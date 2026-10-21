"""Modello di confronto: logit multinomiale con effetti spaziali BYM2 (ICAR + rumore) per comune.

Per ogni variante k (tranne quella di riferimento) e ogni comune i:
    eta_ik = beta_k + sigma_k * (sqrt(rho_k / s) * phi_ik + sqrt(1 - rho_k) * theta_ik)
con phi ICAR sul grafo delle adiacenze comunali, theta ~ N(0, 1) e s il fattore di scala del grafo
(Riebler et al. 2016). Le risposte multiple entrano con il loro peso 1/k.
"""
import numpy as np
import pandas as pd


def grafo(comuni, adiacenze):
    """Archi (i, j) del grafo comunale; le componenti isolate vengono legate al comune più vicino."""
    nomi = comuni.comune.tolist()
    pos = {c: i for i, c in enumerate(nomi)}
    archi = {tuple(sorted((pos[a], pos[b]))) for a, b in adiacenze}
    xy = np.column_stack([comuni.lon * 0.7, comuni.lat])
    while True:
        comp = _componenti(len(nomi), archi)
        if comp.max() == 0:
            break
        piccola = np.bincount(comp).argmin()
        dentro, fuori = np.flatnonzero(comp == piccola), np.flatnonzero(comp != piccola)
        d = np.linalg.norm(xy[dentro][:, None] - xy[fuori][None], axis=2)
        i, j = np.unravel_index(d.argmin(), d.shape)
        archi.add(tuple(sorted((dentro[i], fuori[j]))))
    return np.array(sorted(archi))


def _componenti(n, archi):
    padre = list(range(n))

    def radice(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x
    for a, b in archi:
        padre[radice(a)] = radice(b)
    r = [radice(i) for i in range(n)]
    return pd.factorize(pd.Series(r))[0]


def scala(n, archi):
    """Fattore di scala BYM2: media geometrica delle varianze marginali dell'ICAR vincolato."""
    Q = np.zeros((n, n))
    for a, b in archi:
        Q[a, b] = Q[b, a] = -1
    Q[np.diag_indices(n)] = -Q.sum(1)
    Qp = Q + np.eye(n) * Q.diagonal().max() * np.sqrt(np.finfo(float).eps)
    S = np.linalg.inv(Qp)
    uno = np.ones(n)
    S = S - np.outer(S @ uno, uno @ S) / (uno @ S @ uno)
    return float(np.exp(np.log(np.diag(S)).mean()))


def stima_bym2(N, archi, s, draws=400, tune=400, chains=2, seed=0):
    """N: comuni x varianti (pesi). Restituisce la media a posteriori delle probabilità e un riepilogo."""
    import pymc as pm
    import pytensor.tensor as pt

    n, K = N.shape
    ref = int(N.sum(0).argmax())  # la variante più diffusa fa da riferimento
    altre = [k for k in range(K) if k != ref]
    a, b = archi[:, 0], archi[:, 1]
    with pm.Model():
        beta = pm.Normal("beta", 0, 2, shape=K - 1)
        sigma = pm.HalfNormal("sigma", 1, shape=K - 1)
        rho = pm.Beta("rho", 0.5, 0.5, shape=K - 1)
        theta = pm.Normal("theta", 0, 1, shape=(n, K - 1))
        phi = pm.Flat("phi", shape=(n, K - 1))
        pm.Potential("icar", -0.5 * pt.sum((phi[a] - phi[b]) ** 2))
        pm.Potential("somma_zero", pm.logp(pm.Normal.dist(0, 0.001 * n), phi.sum(0)).sum())
        eta = beta + sigma * (pt.sqrt(rho / s) * phi + pt.sqrt(1 - rho) * theta)
        zeri = pt.zeros((n, 1))
        tutte = pt.concatenate([zeri, eta], axis=1)
        logp = tutte - pt.logsumexp(tutte, axis=1, keepdims=True)
        ordine = [ref] + altre
        pm.Potential("verosimiglianza", pt.sum(N[:, ordine] * logp))
        pm.Deterministic("p", pt.exp(logp))
        tr = pm.sample(draws=draws, tune=tune, chains=chains, cores=chains, random_seed=seed,
                       target_accept=0.9, progressbar=False, compute_convergence_checks=False)
    p_ord = tr.posterior["p"].mean(("chain", "draw")).values
    p = np.empty_like(p_ord)
    p[:, ordine] = p_ord
    post = tr.posterior
    riepilogo = {"rho": post["rho"].mean(("chain", "draw")).values.round(3).tolist(),
                 "sigma": post["sigma"].mean(("chain", "draw")).values.round(3).tolist(),
                 "divergenze": int(tr.sample_stats["diverging"].sum())}
    try:
        import arviz as az
        riepilogo["rhat_max"] = float(az.rhat(tr, var_names=["beta", "sigma", "rho"]).to_array().max())
    except Exception:
        pass
    return p, riepilogo
