import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import torch
from sklearn.cluster import KMeans

from solver.utils_numpy import euclid_dist
from ot.gromov import gromov_wasserstein
from solver.tlb_kl_sinkhorn_solver import TLBSinkhornSolver

path = os.getcwd() + "/output"
if not os.path.isdir(path):
    os.mkdir(path)
path = path + "/plots"
if not os.path.isdir(path):
    os.mkdir(path)


def generate_data(nsample, ratio):
    # Generate first ellipse
    s = np.random.uniform(size=(nsample, 2))
    x1 = np.zeros_like(s)
    x1[:, 0], x1[:, 1] = np.sqrt(s[:, 0]) * np.cos(2 * np.pi * s[:, 1]), 2 * np.sqrt(s[:, 0]) * np.sin(
        2 * np.pi * s[:, 1])
    rot = 0.5 * np.sqrt(2) * np.array([[1, -1], [1, 1]])
    x1 = x1.dot(rot)

    # Generate second circle
    s = np.random.uniform(size=(nsample, 2))
    x2 = np.zeros_like(s)
    x2[:, 0], x2[:, 1] = np.sqrt(s[:, 0]) * np.cos(2 * np.pi * s[:, 1]), np.sqrt(s[:, 0]) * np.sin(
        2 * np.pi * s[:, 1])
    x2 = x2 + np.array([7., 0.])
    x = np.concatenate((x1, x2))

    # Generate second data drom translation
    y = np.concatenate((x1, s + np.array([7., 0.]))) + np.array([0., 7.])
    angle = -1 / 4
    x[:nsample] = x[:nsample].dot(
        np.array([[np.cos(angle * np.pi), np.sin(angle * np.pi)], [-np.sin(angle * np.pi), np.cos(angle * np.pi)]]))
    y[nsample:] = (y[nsample:] - np.mean(y[nsample:], axis=0)).dot(
        np.array([[np.cos(angle * np.pi), np.sin(angle * np.pi)], [-np.sin(angle * np.pi), np.cos(angle * np.pi)]])) \
                  + np.mean(y[nsample:], axis=0)

    # Generate weights
    a, b = np.ones(x.shape[0]) / x.shape[0], np.ones(y.shape[0]) / y.shape[0]
    b[:n1], b[n1:] = (1 - ratio) * b[:n1], ratio * b[n1:]
    b = b / np.sum(b)
    return a, x, b, y


def plot_density_matching(pi, a, x, b, y, idx, alpha, linewidth):
    cmap1 = get_cmap('Blues')
    cmap2 = get_cmap('Reds')
    plt.figure(figsize=(6., 6.))
    plt.scatter(x[:, 0], x[:, 1], c=cmap1(0.3 * (a - np.amin(b)) / np.amin(b) + 0.4), s=10 * (a / a) ** 2, zorder=1)
    plt.scatter(y[:, 0], y[:, 1], c=cmap2(0.3 * (b - np.amin(b)) / np.amin(b) + 0.4), s=10 * (b / a) ** 2, zorder=1)

    # Plot argmax of coupling
    for i in idx:
        m = np.sum(pi[i, :])
        ids = (-pi[i, :]).argsort()[:30]
        for j in ids:
            w = pi[i, j] / m
            t = [x[i][0], y[j][0]]
            u = [x[i][1], y[j][1]]
            plt.plot(t, u, c='k', alpha=w * alpha, linewidth=linewidth, zorder=0)
    plt.xticks([])
    plt.yticks([])
    plt.tight_layout()
    plt.axis('equal')


if __name__ == '__main__':
    n1 = 300
    dim = 2
    rho = 1.
    eps = .01
    n_clust = 20
    compute_balanced = False
    solver = TLBSinkhornSolver(nits=500, nits_sinkhorn=1000, gradient=False, tol=1e-3, tol_sinkhorn=1e-3)

    # Generate gaussian mixtures translated from each other
    a, x, b, y = generate_data(n1, 0.7)
    clf = KMeans(n_clusters=n_clust)
    clf.fit(x)
    idx = np.zeros(n_clust)
    for i in range(n_clust):
        d = clf.transform(x)[:, i]
        idx[i] = np.argmin(d)
    idx = idx.astype(int)

    # Generate costs and transport plan
    Cx, Cy = euclid_dist(x, x), euclid_dist(y, y)

    if compute_balanced:
        pi_b = gromov_wasserstein(Cx, Cy, a, b, loss_fun='square_loss')
        plot_density_matching(pi_b, a, x, b, y, idx, alpha=1., linewidth=.5)
        plt.legend()
        plt.savefig(path + '/fig_matching_plan_balanced.png')
        plt.show()

    Cx, Cy = torch.from_numpy(Cx), torch.from_numpy(Cy)

    rho_list = [0.1]
    peps_list = [2, 1, 0, -1, -2, -3]
    # peps_list = [-2]
    for rho in rho_list:
        pi = None
        for p in peps_list:
            eps = 10 ** p
            print(f"Params = {rho, eps}")
            a, b = torch.from_numpy(a), torch.from_numpy(b)
            pi, gamma = solver.tlb_sinkhorn(a, Cx, b, Cy, rho=rho, eps=eps, init=pi)
            print(f"Sum of transport plans = {pi.sum().item()}")

            # Plot matchings between measures
            a, b = a.data.numpy(), b.data.numpy()
            pi_ = pi.data.numpy()
            plot_density_matching(pi_, a, x, b, y, idx, alpha=1., linewidth=1.)
            plt.legend()
            plt.savefig(path + f'/fig_matching_plan_ugw_rho{rho}_eps{eps}.png')
            plt.show()
