def get_open_uniform_knot_vector(n, d):

    """
    import de_boor_core as core

    core.get_open_uniform_knot_vector(4, 1)
    core.get_open_uniform_knot_vector(4, 2)
    core.get_open_uniform_knot_vector(4, 3)


    Generate an open uniform knot vector for the given CVs and degree.
    """

    return [0] * (d + 1) + [i / (n - d - 1) for i in range(n - d - 1)] + [1] * (d + 1)
    

def get_periodic_uniform_knot_vector(n, d):

    """
    import de_boor_core as core

    core.get_periodic_knot_vector(4, 1)
    core.get_periodic_knot_vector(4, 2)

    Generate a periodic knot vector for the given CVs and degree.
    """

    i = 1.0 / (n + d)
    return [-i * a for a in range(d, 0, -1)] + [i * a for a in range(n + d + 1)] + [i * a + 1 for a in range(1, d + 1)]

def knot_vector(kv_type, cvs, d):

    """
    Generate a knot vector based on the type and degree.
    """

    cvs_copy = cvs[:]

    if kv_type == 'open':
        kv = get_open_uniform_knot_vector(len(cvs), d)

    else:
        kv = get_periodic_uniform_knot_vector(len(cvs), d)

        for i in range(d):
            cvs_copy.insert(0, cvs[len(cvs) - i - 1])
            cvs_copy.append(cvs[i])

    return kv, cvs_copy


def de_boor(n, d, t, kv, tol=0.000001):

    if t + tol > 1:
        return [0.0 if i != n - 1 else 1.0 for i in range(n)]

    weights = [1.0 if kv[i] <= t < kv[i + 1] else 0.0 for i in range(n + d)]

    basis_width = n + d - 1

    for degree in range(1, d + 1):

        for i in range(basis_width):

            if weights[i] == 0 and weights[i + 1] == 0:
                continue

            a_denom = kv[i + degree] - kv[i]
            b_denom = kv[i + degree + 1] - kv[i + 1]

            a = (t - kv[i]) * weights[i] / a_denom if a_denom != 0 else 0.0
            b = (kv[i + degree + 1] - t) * weights[i + 1] / b_denom if b_denom != 0 else 0.0

            weights[i] = a + b

        basis_width -= 1

    return weights[:n]





