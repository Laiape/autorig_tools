"""Build-time compact wrinkle supports with exact smoothing dependencies."""
import math


def plan(patterns, neighbors):
    """Return global/local maps for two smoothing passes without truncating halos."""
    count = len(next(iter(patterns.values()))) if patterns else 0
    if not count or len(neighbors) != 4 or any(len(a) != count for a in neighbors):
        raise ValueError('Use nonempty patterns and four matching neighbor arrays.')
    if any(len(a) != count or any(not math.isfinite(v) for v in a)
           for a in patterns.values()):
        raise ValueError('Pattern arrays must match and contain finite values.')
    if any(type(i) is not int or not 0 <= i < count for a in neighbors for i in a):
        raise ValueError('Neighbor indices must be valid integers.')
    active = sorted(i for i in range(count) if any(a[i] != 0 for a in patterns.values()))

    def expand(indices):
        return sorted(set(indices).union(*(set(a[i] for i in indices) for a in neighbors)))

    first = expand(active)
    compression = expand(first)
    stages = []
    for source, destination in ((compression, first), (first, active)):
        lookup = {global_id: local_id for local_id, global_id in enumerate(source)}
        stages.append({'self': [lookup[i] for i in destination],
                       'neighbors': [[lookup[a[i]] for i in destination] for a in neighbors]})
    return {'version': 1, 'source_vertices': count, 'active': active,
            'compression': compression, 'filter_first': first, 'stages': stages,
            'active_fraction': len(active) / float(count),
            'compression_fraction': len(compression) / float(count)}


def validate_metadata(metadata, vertices):
    if metadata.get('version') != 1 or metadata.get('source_vertices') != vertices:
        raise ValueError('Regional support does not match the source topology.')
    return metadata
