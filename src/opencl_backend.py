"""Backend GPU OpenCL (G5) — residente, com fallback CPU.

Porta o scoring/apply/erro do `cpu_backend.py` para OpenCL C portavel
(compila no device OpenCL C 2.0 do Adrenalin; roda tambem em 1.2). Nao usa
SPIR-V/C++/SVM: so o subset basico, para maxima compatibilidade.

Arquitetura (residente): target/current/mask/emap vivem na GPU o run todo;
o host so envia o lote de candidatos e recebe os deltas. Espelha
`_score_one` (inclusive peso de borda e penalidade de spill).
"""
import numpy as np

_KERNEL_SRC = r"""
#ifndef UCHAR4_A
#define UCHAR4_A 255
#endif

__kernel void score_batch(
    __global const uchar4 *target,
    __global const uchar4 *current,
    __global const uchar  *mask,
    __global const float  *emap,
    __global const float  *cands,
    __global float *out_delta,
    __global float *out_rgba,
    __global int   *out_cnt,
    const int W, const int H, const int n,
    const float spill_w)
{
    /* Um work-group por candidato: as threads cooperam sobre a bbox.
       Evita a divergencia SIMT de 1 work-item/candidato (bboxes de tamanhos
       muito diferentes travavam a wave inteira na maior). */
    int g = get_group_id(0);
    int lid = get_local_id(0);
    int ls = get_local_size(0);
    if (g >= n) return;

    float cx = cands[g * 6 + 0];
    float cy = cands[g * 6 + 1];
    float rx = cands[g * 6 + 2];
    float ry = cands[g * 6 + 3];
    float ang = cands[g * 6 + 4];
    float alpha = cands[g * 6 + 5];

    if (rx < 1.0f) rx = 1.0f;
    if (ry < 1.0f) ry = 1.0f;
    if (alpha < 8.0f) alpha = 8.0f;
    if (alpha > 255.0f) alpha = 255.0f;
    float a = alpha / 255.0f;
    float inv_a = 1.0f / a;
    float om_a = 1.0f - a;
    float rad = ang * 0.017453292519943295f;
    float ca = cos(rad);
    float sa = sin(rad);
    float ex = fabs(rx * ca) + fabs(ry * sa);
    float ey = fabs(rx * sa) + fabs(ry * ca);
    int x0 = (int)(cx - ex), x1 = (int)(cx + ex);
    int y0 = (int)(cy - ey), y1 = (int)(cy + ey);
    x0 = max(x0, 0); y0 = max(y0, 0);
    x1 = min(x1, W - 1); y1 = min(y1, H - 1);
    float inv_rx2 = 1.0f / (rx * rx);
    float inv_ry2 = 1.0f / (ry * ry);

    __local float red[8][256];
    __local int ired[256];

    float sr = 0.0f, sg = 0.0f, sb = 0.0f, wsum = 0.0f, errb = 0.0f;
    int cnt = 0, spill = 0;
    bool valid = (x1 >= x0) && (y1 >= y0);
    if (valid) {
        for (int y = y0; y <= y1; ++y) {
            float dy = (float)y - cy;
            for (int x = x0 + lid; x <= x1; x += ls) {
                float dx = (float)x - cx;
                float lx = dx * ca + dy * sa;
                float ly = -dx * sa + dy * ca;
                if (lx * lx * inv_rx2 + ly * ly * inv_ry2 > 1.0f) continue;
                int idx = y * W + x;
                if (mask[idx] == 0) { spill++; continue; }
                float w = emap[idx];
                uchar4 tc = target[idx];
                uchar4 cc = current[idx];
                float tr = (float)tc.x, tg = (float)tc.y, tb = (float)tc.z;
                float cr = (float)cc.x, cg = (float)cc.y, cb = (float)cc.z;
                sr += w * (tr - om_a * cr) * inv_a;
                sg += w * (tg - om_a * cg) * inv_a;
                sb += w * (tb - om_a * cb) * inv_a;
                wsum += w;
                float dr = tr - cr, dg = tg - cg, db = tb - cb;
                errb += w * (dr * dr + dg * dg + db * db);
                cnt++;
            }
        }
    }
    red[0][lid] = sr; red[1][lid] = sg; red[2][lid] = sb;
    red[3][lid] = wsum; red[4][lid] = errb; red[6][lid] = (float)cnt;
    ired[lid] = spill;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (int s = ls >> 1; s > 0; s >>= 1) {
        if (lid < s) {
            red[0][lid] += red[0][lid + s];
            red[1][lid] += red[1][lid + s];
            red[2][lid] += red[2][lid + s];
            red[3][lid] += red[3][lid + s];
            red[4][lid] += red[4][lid + s];
            red[6][lid] += red[6][lid + s];
            ired[lid] += ired[lid + s];
        }
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    __local float s_br, s_bg, s_bb, s_errb;
    if (lid == 0) {
        float ws = red[3][0];
        if (ws > 0.0f) {
            s_br = clamp(red[0][0] / ws, 0.0f, 255.0f);
            s_bg = clamp(red[1][0] / ws, 0.0f, 255.0f);
            s_bb = clamp(red[2][0] / ws, 0.0f, 255.0f);
        } else { s_br = 0.0f; s_bg = 0.0f; s_bb = 0.0f; }
        s_errb = red[4][0];
    }
    barrier(CLK_LOCAL_MEM_FENCE);
    float br = s_br, bg = s_bg, bb = s_bb;
    float errb_tot = s_errb;
    int spill_tot = ired[0];
    int cnt_tot = (int)red[6][0];

    float erra = 0.0f;
    if (valid && cnt_tot > 0) {
        for (int y = y0; y <= y1; ++y) {
            float dy = (float)y - cy;
            for (int x = x0 + lid; x <= x1; x += ls) {
                float dx = (float)x - cx;
                float lx = dx * ca + dy * sa;
                float ly = -dx * sa + dy * ca;
                if (lx * lx * inv_rx2 + ly * ly * inv_ry2 > 1.0f) continue;
                int idx = y * W + x;
                if (mask[idx] == 0) continue;
                float w = emap[idx];
                uchar4 tc = target[idx];
                uchar4 cc = current[idx];
                float nar = a * br + om_a * (float)cc.x;
                float nag = a * bg + om_a * (float)cc.y;
                float nab = a * bb + om_a * (float)cc.z;
                float dr = (float)tc.x - nar;
                float dg = (float)tc.y - nag;
                float db = (float)tc.z - nab;
                erra += w * (dr * dr + dg * dg + db * db);
            }
        }
    }
    red[5][lid] = erra;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (int s = ls >> 1; s > 0; s >>= 1) {
        if (lid < s) red[5][lid] += red[5][lid + s];
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    if (lid == 0) {
        out_delta[g] = red[5][0] - errb_tot + spill_w * (float)spill_tot;
        out_rgba[g * 4 + 0] = br;
        out_rgba[g * 4 + 1] = bg;
        out_rgba[g * 4 + 2] = bb;
        out_rgba[g * 4 + 3] = alpha;
        out_cnt[g] = cnt_tot;
    }
}

__kernel void apply_ellipse(
    __global uchar4 *current,
    __global const uchar *mask,
    const int W, const int H,
    const int xo, const int yo,
    const float cx, const float cy,
    const float rx0, const float ry0,
    const float ang_deg, const float alpha,
    const float cr0, const float cg0, const float cb0)
{
    int x = xo + get_global_id(0);
    int y = yo + get_global_id(1);
    if (x < 0 || y < 0 || x >= W || y >= H) return;
    if (mask[y * W + x] == 0) return;
    float rx = rx0 < 1.0f ? 1.0f : rx0;
    float ry = ry0 < 1.0f ? 1.0f : ry0;
    float a = alpha / 255.0f;
    if (a < 0.0f) a = 0.0f;
    if (a > 1.0f) a = 1.0f;
    float om = 1.0f - a;
    float rad = ang_deg * 0.017453292519943295f;
    float ca = cos(rad);
    float sa = sin(rad);
    float dx = (float)x - cx;
    float dy = (float)y - cy;
    float lx = dx * ca + dy * sa;
    float ly = -dx * sa + dy * ca;
    if (lx * lx / (rx * rx) + ly * ly / (ry * ry) > 1.0f) return;
    int idx = y * W + x;
    uchar4 c = current[idx];
    current[idx] = (uchar4)(
        (uchar)clamp(a * cr0 + om * (float)c.x, 0.0f, 255.0f),
        (uchar)clamp(a * cg0 + om * (float)c.y, 0.0f, 255.0f),
        (uchar)clamp(a * cb0 + om * (float)c.z, 0.0f, 255.0f),
        (uchar)255);
}

__kernel void error_stage1(
    __global const uchar4 *target,
    __global const uchar4 *current,
    __global const uchar *mask,
    __global float *partials,
    const int npx)
{
    int gid = get_global_id(0);
    int gsize = get_global_size(0);
    float acc = 0.0f;
    for (int i = gid; i < npx; i += gsize) {
        if (mask[i] == 0) continue;
        uchar4 t = target[i];
        uchar4 c = current[i];
        float dr = (float)t.x - (float)c.x;
        float dg = (float)t.y - (float)c.y;
        float db = (float)t.z - (float)c.z;
        acc += dr * dr + dg * dg + db * db;
    }
    __local float red[256];
    int lid = get_local_id(0);
    int ls = get_local_size(0);
    red[lid] = acc;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (int s = ls >> 1; s > 0; s >>= 1) {
        if (lid < s) red[lid] += red[lid + s];
        barrier(CLK_LOCAL_MEM_FENCE);
    }
    if (lid == 0) partials[get_group_id(0)] = red[0];
}
"""

_ctx = None
_queue = None
_program = None
_device_name = None
_build_error = None


def available():
    """True se ha um device OpenCL utilizavel."""
    try:
        import pyopencl as cl
        for p in cl.get_platforms():
            if p.get_devices():
                return True
    except Exception:
        return False
    return False


def _pick_device(cl):
    best = None
    for p in cl.get_platforms():
        for d in p.get_devices():
            is_gpu = bool(d.type & cl.device_type.GPU)
            if is_gpu:
                return p, d
            if best is None:
                best = (p, d)
    if best is None:
        raise RuntimeError("nenhum device OpenCL encontrado")
    return best


def _get_context():
    """Contexto/queue/programa singleton (com cache)."""
    global _ctx, _queue, _program, _device_name, _build_error
    if _ctx is not None:
        return _ctx, _queue, _program, _device_name
    if _build_error is not None:
        raise RuntimeError(_build_error)
    try:
        import pyopencl as cl
        _, dev = _pick_device(cl)
        _ctx = cl.Context([dev])
        _queue = cl.CommandQueue(_ctx)
        _program = cl.Program(_ctx, _KERNEL_SRC).build(
            options=["-cl-fast-relaxed-math", "-cl-mad-enable"])
        _device_name = dev.name
    except Exception as e:  # fallback: registra e propaga
        _build_error = f"OpenCL indisponivel: {e}"
        raise RuntimeError(_build_error)
    return _ctx, _queue, _program, _device_name


class GpuScorer:
    """Scoring/apply/erro residentes na GPU (mesma interface semantica do CPU)."""

    def __init__(self, target, current, mask, emap, spill_w=0.0, local_size=128):
        import pyopencl as cl
        ctx, queue, program, _ = _get_context()
        self.cl = cl
        self.ctx = ctx
        self.queue = queue
        self.program = program
        self.ls = int(local_size)
        self.spill_w = float(spill_w)
        self.k_score = cl.Kernel(program, "score_batch")
        self.k_apply = cl.Kernel(program, "apply_ellipse")
        self.k_err = cl.Kernel(program, "error_stage1")
        H, W = mask.shape
        self.H, self.W = int(H), int(W)
        self.npx = H * W
        self.n_mask = int(mask.sum())
        mf = cl.mem_flags

        rgba = np.empty((H, W, 4), dtype=np.uint8)
        rgba[:, :, :3] = target
        rgba[:, :, 3] = 255
        cur = np.empty((H, W, 4), dtype=np.uint8)
        cur[:, :, :3] = current
        cur[:, :, 3] = 255
        self.d_target = cl.Buffer(
            ctx, mf.READ_ONLY | mf.COPY_HOST_PTR,
            hostbuf=np.ascontiguousarray(rgba))
        self.d_current = cl.Buffer(
            ctx, mf.READ_WRITE | mf.COPY_HOST_PTR,
            hostbuf=np.ascontiguousarray(cur))
        self.d_mask = cl.Buffer(
            ctx, mf.READ_ONLY | mf.COPY_HOST_PTR,
            hostbuf=np.ascontiguousarray(mask.astype(np.uint8).ravel()))
        self.d_emap = cl.Buffer(
            ctx, mf.READ_ONLY | mf.COPY_HOST_PTR,
            hostbuf=np.ascontiguousarray(emap.astype(np.float32).ravel()))

        self._cap = 0
        self._err_gsize = 0
        self._alloc_batch(65536)
        self._alloc_error(1 << 20)

    # ---- alocacoes reutilizaveis -------------------------------------
    def _alloc_batch(self, n):
        if n <= self._cap:
            return
        n = int(n * 1.5) + 1
        mf = self.cl.mem_flags
        self.d_cands = self.cl.Buffer(self.ctx, mf.READ_ONLY, n * 6 * 4)
        self.d_delta = self.cl.Buffer(self.ctx, mf.WRITE_ONLY, n * 4)
        self.d_rgba = self.cl.Buffer(self.ctx, mf.WRITE_ONLY, n * 4 * 4)
        self.d_cnt = self.cl.Buffer(self.ctx, mf.WRITE_ONLY, n * 4)
        self._cap = n

    def _alloc_error(self, npx):
        gsize = ((npx + self.ls - 1) // self.ls) * self.ls
        nparts = gsize // self.ls
        if nparts <= self._err_gsize:
            return
        mf = self.cl.mem_flags
        self.d_partials = self.cl.Buffer(self.ctx, mf.WRITE_ONLY,
                                         nparts * 4)
        self._err_gsize = nparts

    # ---- interface ---------------------------------------------------
    def score(self, cands):
        n = len(cands)
        if n == 0:
            return []
        c = np.ascontiguousarray(cands, dtype=np.float32)
        self._alloc_batch(n)
        self.cl.enqueue_copy(self.queue, self.d_cands, c)
        gsize = n * self.ls  # um work-group por candidato
        self.k_score(
            self.queue, (gsize,), (self.ls,),            self.d_target, self.d_current, self.d_mask, self.d_emap,
            self.d_cands, self.d_delta, self.d_rgba, self.d_cnt,
            np.int32(self.W), np.int32(self.H), np.int32(n),
            np.float32(self.spill_w))
        delta = np.empty(n, dtype=np.float32)
        rgba = np.empty(n * 4, dtype=np.float32)
        cnt = np.empty(n, dtype=np.int32)
        self.cl.enqueue_copy(self.queue, delta, self.d_delta)
        self.cl.enqueue_copy(self.queue, rgba, self.d_rgba)
        self.cl.enqueue_copy(self.queue, cnt, self.d_cnt)
        self.queue.finish()
        rgba = rgba.reshape(n, 4)
        from .scoring import BatchScores
        return BatchScores(delta, rgba[:, 0], rgba[:, 1], rgba[:, 2],
                           c[:, 5], cnt)

    def apply(self, cx, cy, rx, ry, ang, r, g, b, a):
        import math
        rad = math.radians(ang)
        ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
        ex = rx * ca + ry * sa
        ey = rx * sa + ry * ca
        x0 = max(0, int(cx - ex))
        y0 = max(0, int(cy - ey))
        x1 = min(self.W - 1, int(cx + ex))
        y1 = min(self.H - 1, int(cy + ey))
        bw = x1 - x0 + 1
        bh = y1 - y0 + 1
        if bw <= 0 or bh <= 0:
            return
        self.k_apply(
            self.queue, (bw, bh), None,
            self.d_current, self.d_mask, np.int32(self.W), np.int32(self.H),
            np.int32(x0), np.int32(y0),
            np.float32(cx), np.float32(cy), np.float32(rx), np.float32(ry),
            np.float32(ang), np.float32(a),
            np.float32(r), np.float32(g), np.float32(b))

    def error(self):
        self._alloc_error(self.npx)
        gsize = ((self.npx + self.ls - 1) // self.ls) * self.ls
        nparts = gsize // self.ls
        self.k_err(
            self.queue, (gsize,), (self.ls,),
            self.d_target, self.d_current, self.d_mask, self.d_partials,
            np.int32(self.npx))
        parts = np.empty(nparts, dtype=np.float32)
        self.cl.enqueue_copy(self.queue, parts, self.d_partials)
        self.queue.finish()
        tot = float(parts.sum())
        if self.n_mask == 0:
            return 0.0
        return (tot / (self.n_mask * 3 * 255.0 * 255.0)) ** 0.5

    def read_current(self):
        out = np.empty((self.H, self.W, 4), dtype=np.uint8)
        self.cl.enqueue_copy(self.queue, out, self.d_current)
        self.queue.finish()
        return np.ascontiguousarray(out[:, :, :3])
