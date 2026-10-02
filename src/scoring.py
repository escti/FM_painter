"""Resultado de um lote de scoring, apoiado em arrays (sem listas de tuplas).

Evita montar N tuplas Python no caminho GPU (era o gargalo apos o kernel
ficar rapido). A interface antiga (iteracao/indexacao) continua valendo.
"""
import numpy as np


class BatchScores:
    __slots__ = ("delta", "r", "g", "b", "alpha", "cnt")

    def __init__(self, delta, r, g, b, alpha, cnt):
        self.delta = delta
        self.r = r
        self.g = g
        self.b = b
        self.alpha = alpha
        self.cnt = cnt

    def __len__(self):
        return int(len(self.delta))

    def get(self, i):
        i = int(i)
        return (float(self.delta[i]), float(self.r[i]), float(self.g[i]),
                float(self.b[i]), float(self.alpha[i]), int(self.cnt[i]))

    def __getitem__(self, i):
        return self.get(i)

    def __iter__(self):
        for i in range(len(self)):
            yield self.get(i)

    def argmin(self):
        return int(np.argmin(self.delta))

    def argsort(self, k):
        return np.argsort(self.delta)[:int(k)]
