"""Distil county centroids from the committed TopoJSON.

The collectors browse wants one number — how far away somebody is — and a
county-to-county great circle is honest enough for a line on a card. This
reads ``static/data/counties-10m.json`` (the same file the map draws),
decodes the delta-encoded arcs, takes the shoelace centroid of each
county's largest exterior ring, and writes ``apps/core/data/
county_centroids.json`` as ``{fips: [lon, lat]}``.

Run it again only if the topology file ever changes:

    python utilities/build_county_centroids.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'static', 'data', 'counties-10m.json')
OUT = os.path.join(ROOT, 'apps', 'core', 'data', 'county_centroids.json')


def decode_arcs(topo):
    scale = topo['transform']['scale']
    translate = topo['transform']['translate']
    arcs = []
    for arc in topo['arcs']:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * scale[0] + translate[0],
                           y * scale[1] + translate[1]))
        arcs.append(points)
    return arcs


def ring_points(ring, arcs):
    points = []
    for i, arc_index in enumerate(ring):
        arc = arcs[arc_index] if arc_index >= 0 else arcs[~arc_index][::-1]
        points.extend(arc if i == 0 else arc[1:])
    return points


def area_and_centroid(points):
    """Shoelace over lon/lat — planar, which is fine at county scale."""
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) < 1e-12:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    area *= 0.5
    return abs(area), cx / (6 * area), cy / (6 * area)


def main():
    with open(SRC, encoding='utf-8') as fh:
        topo = json.load(fh)
    arcs = decode_arcs(topo)

    centroids = {}
    for geometry in topo['objects']['counties']['geometries']:
        if geometry['type'] == 'MultiPolygon':
            polygons = geometry['arcs']
        elif geometry['type'] == 'Polygon':
            polygons = [geometry['arcs']]
        else:
            continue
        best = None
        for polygon in polygons:
            points = ring_points(polygon[0], arcs)  # first ring is exterior
            candidate = area_and_centroid(points)
            if best is None or candidate[0] > best[0]:
                best = candidate
        centroids[str(geometry['id'])] = [round(best[1], 4), round(best[2], 4)]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(centroids, fh, separators=(',', ':'), sort_keys=True)
    print(f'{len(centroids)} county centroids -> {OUT}')

    lycoming = centroids.get('42081')
    cameron = centroids.get('42023')
    print('Lycoming PA:', lycoming, '| Cameron PA:', cameron)


if __name__ == '__main__':
    main()
