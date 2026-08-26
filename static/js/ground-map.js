/* The ground map — an engraved survey map, not a web map.
 *
 * One component, two lenses, three depths. Fill answers the lens's question
 * — what's listed (marketplace supply) or what's owned (a collector's
 * ground) — and the brass answers the other one, so the two together answer
 * the only question a collector brings to a map: where can I get something
 * I haven't got. Country → state → county; there is no third zoom, because
 * there is nothing below county level worth drawing.
 *
 * Flat parchment, hairline borders, fixed-count buckets so the legend is a
 * promise rather than a decoration. No basemap, no pins, no animated
 * draw-in, no shadow. Render once, and hold.
 *
 * Loads after js/vendor/d3.v7.min.js and js/vendor/topojson-client.min.js —
 * both self-hosted, because the last map died waiting on somebody's CDN.
 */
(function () {
    'use strict';

    /* Fixed counts, never scaled to the maximum — the designer's charge
     * against the old map was exactly that no two counties shared a shade
     * and the legend could never be honest. */
    const LISTED_RAMP = [
        [0, '#f0ede6', 'None listed'],
        [1, '#e8f5e2', 'One'],
        [2, '#b9d6a8', 'Two to four'],
        [5, '#7fae6a', 'Five to nine'],
        [10, '#3f7a2c', 'Ten to twenty-four'],
        [25, '#1a5c0d', 'Twenty-five and up'],
    ];
    const OWNED_UNIT_RAMP = [
        [0, '#efe9da', 'A gap — none owned'],
        [1, '#8fa678', 'One owned'],
        [2, '#4d6b3f', 'Two or three'],
        [4, '#26331f', 'Four or more'],
    ];
    const OWNED_US_RAMP = [
        [0, '#efe9da', 'None yet'],
        [1, '#8fa678', '1 to 19'],
        [20, '#4d6b3f', '20 to 99'],
        [100, '#26331f', '100 or more'],
    ];

    const INK = {
        forest: '#26331f', night: '#1b2416', brass: '#a07a26',
        hairline: '#b0a88a', context: '#dcd6c6', quiet: '#8c8f80',
        cream: 'rgba(244,241,232,.92)',
    };

    function bucketColor(ramp, n) {
        let color = ramp[0][1];
        for (const [min, c] of ramp) if (n >= min) color = c;
        return color;
    }

    function bucketIndex(ramp, n) {
        let idx = 0;
        ramp.forEach(([min], i) => { if (n >= min) idx = i; });
        return idx;
    }

    /* Dark ink on the pale fills, cream on the dark ones. */
    function inkFor(hex) {
        const v = parseInt(hex.slice(1), 16);
        const lum = 0.2126 * (v >> 16) + 0.7152 * ((v >> 8) & 255) + 0.0722 * (v & 255);
        return lum > 128 ? '#1b2416' : INK.cream;
    }

    function darker(hex) {
        const c = d3.color(hex);
        return c ? c.darker(0.35).formatHex() : hex;
    }

    function esc(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function el(tag, className, html) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (html != null) node.innerHTML = html;
        return node;
    }

    let instances = 0;

    class GroundMap {
        constructor(root, opts) {
            this.root = root;
            this.opts = Object.assign({
                api: '/api/map/',
                topo: null,
                lens: 'listed',
                lenses: null,          // more than one → chips switch the lens
                scope: 'us',
                state: null,
                collector: '',
                authed: false,
                small: false,
                height: null,
                links: {},
            }, opts || {});
            this.lens = this.opts.lens;
            this.lenses = this.opts.lenses || [this.lens];
            this.gapsOnly = false;
            this.selection = null;
            this.uid = 'gm' + (instances += 1);
            this.cache = {};           // api payloads by scope key
            this.startedAt = this.opts.scope;

            if (typeof d3 === 'undefined' || typeof topojson === 'undefined') {
                this.fail(); return;
            }

            this.build();
            this.topoPromise = fetch(this.opts.topo).then((r) => {
                if (!r.ok) throw new Error('topo ' + r.status);
                return r.json();
            });
            this.show(this.opts.scope, this.opts.state);
        }

        /* ── skeleton ──────────────────────────────────────────────── */

        build() {
            this.root.classList.add('gm', this.opts.small ? 'gm--small' : 'gm--full');
            if (!this.opts.small) {
                this.controls = el('div', 'gm-controls');
                this.root.appendChild(this.controls);
            }
            const body = el('div', 'gm-body');
            this.figure = el('div', 'gm-figure');
            body.appendChild(this.figure);
            if (!this.opts.small) {
                this.aside = el('aside', 'gm-aside');
                body.appendChild(this.aside);
            }
            this.root.appendChild(body);
            this.note = el('p', 'gm-note');
            this.root.appendChild(this.note);

            this.tip = el('div', 'gm-tip');
            this.tip.style.display = 'none';
            document.body.appendChild(this.tip);
        }

        fail() {
            this.root.classList.add('gm');
            this.root.innerHTML = '<p class="gm-fail">The map couldn’t load just now '
                + '— the counts on the rest of the page still stand.</p>';
        }

        /* ── data ──────────────────────────────────────────────────── */

        async load(stateCode) {
            const key = stateCode || 'us';
            if (this.cache[key]) return this.cache[key];
            const params = new URLSearchParams();
            if (stateCode) params.set('state', stateCode);
            if (this.opts.collector) params.set('collector', this.opts.collector);
            const url = this.opts.api + (params.toString() ? '?' + params.toString() : '');
            const response = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('api ' + response.status);
            const data = await response.json();
            this.cache[key] = data;
            return data;
        }

        async show(scope, stateCode) {
            this.depth = scope;
            this.stateCode = stateCode || null;
            this.selection = null;
            try {
                const [topo, data] = await Promise.all([
                    this.topoPromise, this.load(scope === 'state' ? stateCode : null),
                ]);
                this.topo = topo;
                this.data = data;
                this.render();
            } catch (err) {
                this.fail();
            }
        }

        render() {
            if (this.depth === 'state' && this.data.grid) this.renderGrid();
            else if (this.depth === 'state') this.renderState();
            else this.renderUS();
            this.renderControls();
            this.renderAside();
            this.renderNote();
            /* A re-render (lens or gaps toggle) redraws the paper; the
             * chosen county stays chosen on the fresh sheet. */
            if (this.selection && this.depth === 'state') this.select(this.selection);
        }

        value(row) {
            return this.lens === 'owned' ? (row.owned || 0) : (row.listed || 0);
        }

        ramp() {
            if (this.lens === 'owned') {
                return this.depth === 'us' ? OWNED_US_RAMP : OWNED_UNIT_RAMP;
            }
            return LISTED_RAMP;
        }

        /* ── controls row ──────────────────────────────────────────── */

        renderControls() {
            if (!this.controls) return;
            this.controls.innerHTML = '';

            if (this.depth === 'state') {
                const back = el('button', 'gm-chip', '← Whole country');
                back.type = 'button';
                back.addEventListener('click', () => this.show('us', null));
                this.controls.appendChild(back);
            }

            if (this.lenses.length > 1) {
                const labels = { owned: 'My collection', listed: 'For sale now' };
                for (const lens of this.lenses) {
                    const chip = el('button',
                        'gm-chip' + (lens === this.lens ? ' gm-chip--on' : ''),
                        labels[lens] || lens);
                    chip.type = 'button';
                    chip.addEventListener('click', () => {
                        if (this.lens === lens) return;
                        this.lens = lens;
                        this.selection = null;
                        this.render();
                    });
                    this.controls.appendChild(chip);
                }
            }

            /* 9e: "Only my gaps makes that the whole view." */
            if (this.lens === 'listed' && this.opts.authed && this.depth === 'state') {
                const gaps = el('button',
                    'gm-chip' + (this.gapsOnly ? ' gm-chip--on' : ''), 'Only my gaps');
                gaps.type = 'button';
                gaps.addEventListener('click', () => {
                    this.gapsOnly = !this.gapsOnly;
                    this.render();
                });
                this.controls.appendChild(gaps);
            }

            const hint = el('span', 'gm-controls-hint');
            hint.textContent = this.depth === 'us'
                ? 'Click a state to open its ' + (this.lens === 'owned' ? 'ground' : 'counties')
                : 'Click a ' + (this.data.unit_label || 'county').toLowerCase() + ' to open it';
            this.controls.appendChild(hint);
        }

        /* ── the country ───────────────────────────────────────────── */

        renderUS() {
            const rows = new Map((this.data.states || []).map((s) => [s.fips, s]));
            const states = topojson.feature(this.topo, this.topo.objects.states);
            const { svg, w, h, path } = this.frame(states, 0.545);
            const ramp = this.ramp();

            const fill = (d) => {
                const row = rows.get(d.id);
                if (!row || !row.active) return '#f5f2ea';
                return bucketColor(ramp, this.value(row));
            };

            const shapes = svg.append('g');
            shapes.selectAll('path').data(states.features).join('path')
                .attr('d', path)
                .attr('fill', fill)
                .attr('stroke', INK.hairline).attr('stroke-width', 0.6)
                .attr('opacity', (d) => {
                    const row = rows.get(d.id);
                    return row && row.active ? 1 : 0.35;
                })
                .style('cursor', (d) => {
                    const row = rows.get(d.id);
                    return row && row.active ? 'pointer' : 'default';
                })
                .on('pointermove', (event, d) => this.tipUS(event, rows.get(d.id)))
                .on('pointerleave', () => this.hideTip())
                .on('click', (event, d) => {
                    const row = rows.get(d.id);
                    if (!row || !row.active) return;
                    this.hideTip();
                    if (this.opts.small && this.opts.links.mapPage) {
                        window.location.href = this.opts.links.mapPage
                            + '?state=' + encodeURIComponent(row.code);
                        return;
                    }
                    if (!this.opts.small) this.show('state', row.code);
                })
                .on('pointerenter', function () {
                    d3.select(this).attr('stroke', INK.forest).attr('stroke-width', 1.4).raise();
                })
                .on('pointerout', function () {
                    d3.select(this).attr('stroke', INK.hairline).attr('stroke-width', 0.6);
                });

            /* The other lens's mark: held ground under the listed lens. */
            if (this.lens === 'listed') {
                this.innerRule(svg, path,
                    states.features.filter((d) => {
                        const row = rows.get(d.id);
                        return row && row.active && row.owned > 0;
                    }));
            }

            const labelMin = w * h * 0.0026;
            svg.append('g').attr('class', 'gm-labels')
                .selectAll('text')
                .data(states.features.filter((d) => path.area(d) > labelMin))
                .join('text')
                .attr('transform', (d) => 'translate(' + path.centroid(d) + ')')
                .attr('text-anchor', 'middle').attr('dy', '0.32em')
                .attr('font-size', this.opts.small ? 7 : 8.5)
                .attr('fill', (d) => {
                    const row = rows.get(d.id);
                    if (!row || !row.active) return '#b3ad9c';
                    return inkFor(bucketColor(ramp, this.value(row)));
                })
                .text((d) => {
                    const row = rows.get(d.id);
                    return ((row && row.name) || '').slice(0, 14).toUpperCase();
                });
        }

        /* ── one state ─────────────────────────────────────────────── */

        stateFeatures() {
            const prefix = this.data.state_fips;
            const geoms = this.topo.objects.counties.geometries
                .filter((g) => String(g.id).slice(0, 2) === prefix);
            return {
                fc: topojson.feature(this.topo,
                    { type: 'GeometryCollection', geometries: geoms }),
                geoms,
            };
        }

        renderState() {
            const byFips = new Map(
                (this.data.units || []).filter((u) => u.fips).map((u) => [u.fips, u]));
            const { fc, geoms } = this.stateFeatures();
            if (!fc.features.length) { this.renderGrid(); return; }
            this.neighborIndex = topojson.neighbors(geoms);
            this.stateGeoms = geoms;

            const { svg, w, h, path } = this.frame(fc, 0.62);
            const ramp = this.ramp();
            const defs = svg.append('defs');

            /* Context, not content: the neighbouring states, faint. */
            const allStates = topojson.feature(this.topo, this.topo.objects.states);
            svg.insert('g', ':first-child').selectAll('path')
                .data(allStates.features.filter((d) => d.id !== this.data.state_fips))
                .join('path')
                .attr('d', path)
                .attr('fill', 'none')
                .attr('stroke', INK.context).attr('stroke-width', 0.5);
            svg.select('g').selectAll('text')
                .data(allStates.features.filter((d) => {
                    if (d.id === this.data.state_fips) return false;
                    const c = path.centroid(d);
                    return c[0] > 0 && c[0] < w && c[1] > 0 && c[1] < h;
                }))
                .join('text')
                .attr('class', 'gm-context-name')
                .attr('transform', (d) => 'translate(' + path.centroid(d) + ')')
                .attr('text-anchor', 'middle')
                .text((d) => (d.properties.name || '').toUpperCase());

            /* Gold hatching: something for sale on ground the collector
             * doesn't hold — the one thing they scan for. */
            const hatchId = this.uid + '-hatch';
            const hatch = defs.append('pattern').attr('id', hatchId)
                .attr('width', 5).attr('height', 5)
                .attr('patternUnits', 'userSpaceOnUse')
                .attr('patternTransform', 'rotate(45)');
            hatch.append('rect').attr('width', 5).attr('height', 5).attr('fill', '#f3ecda');
            hatch.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 5)
                .attr('stroke', '#c9a44f').attr('stroke-width', 1.4);

            const rowFor = (d) => byFips.get(String(d.id));
            const fill = (d) => {
                const row = rowFor(d);
                if (!row) return '#f5f2ea';
                if (this.lens === 'owned') {
                    if (!row.owned && row.listed) return 'url(#' + hatchId + ')';
                    return bucketColor(ramp, row.owned);
                }
                if (this.gapsOnly && row.owned > 0) return '#f0ede6';
                return bucketColor(ramp, row.listed);
            };

            this.shapePaths = svg.append('g').selectAll('path')
                .data(fc.features).join('path')
                .attr('d', path)
                .attr('fill', fill)
                .attr('stroke', INK.hairline).attr('stroke-width', 0.5)
                .style('cursor', 'pointer')
                .on('pointermove', (event, d) => this.tipUnit(event, rowFor(d)))
                .on('pointerleave', () => this.hideTip())
                .on('pointerenter', function () {
                    d3.select(this).attr('stroke', INK.forest).attr('stroke-width', 2).raise();
                })
                .on('pointerout', function () {
                    d3.select(this).attr('stroke', INK.hairline).attr('stroke-width', 0.5);
                })
                .on('click', (event, d) => {
                    const row = rowFor(d);
                    if (!row) return;
                    if (this.touchOnce(event, row)) return;
                    this.hideTip();
                    if (!this.opts.small) this.select(row);
                });

            /* Marks from the other lens. */
            if (this.lens === 'listed') {
                this.innerRule(svg, path,
                    fc.features.filter((d) => (rowFor(d) || {}).owned > 0));
            } else {
                svg.append('g').selectAll('path')
                    .data(fc.features.filter((d) => {
                        const row = rowFor(d);
                        return row && !row.owned && row.listed;
                    }))
                    .join('path')
                    .attr('d', path).attr('fill', 'none')
                    .attr('stroke', INK.brass).attr('stroke-width', 1.3)
                    .attr('pointer-events', 'none');
            }

            this.selGroup = svg.append('g').attr('pointer-events', 'none');
            this.statePath = path;
            this.stateFC = fc;

            /* County labels: only where the shape can carry the word. */
            const labels = svg.append('g').attr('class', 'gm-labels')
                .attr('pointer-events', 'none');
            const fontSize = this.opts.small ? 7 : 10;
            for (const d of fc.features) {
                const row = rowFor(d);
                if (!row) continue;
                if (this.lens === 'listed' && !row.listed && !this.opts.small) continue;
                const bounds = path.bounds(d);
                const boxW = bounds[1][0] - bounds[0][0];
                const boxH = bounds[1][1] - bounds[0][1];
                const estimate = row.name.length * fontSize * 0.68;
                if (boxW * 0.94 < estimate || boxH < fontSize + 5) continue;
                const centroid = path.centroid(d);
                const shade = fill(d);
                const ink = !row.owned && !row.listed ? INK.quiet
                    : (shade.charAt(0) === '#' ? inkFor(shade) : '#1b2416');
                const text = labels.append('text')
                    .attr('transform', 'translate(' + centroid + ')')
                    .attr('text-anchor', 'middle').attr('dy', '0.32em')
                    .attr('font-size', fontSize)
                    .attr('fill', ink)
                    .text(row.name.toUpperCase());
                /* Counts only appear above 40 — the shade carries the rest. */
                if (this.lens === 'listed' && row.listed > 40 && !this.opts.small) {
                    text.append('tspan')
                        .attr('x', 0).attr('dy', 12)
                        .attr('class', 'gm-count')
                        .text(row.listed);
                }
            }
        }

        /* Brass rule inside the border: a mark on the map, not a change
         * to it. An inner stroke is a clipped double-width stroke. */
        innerRule(svg, path, features) {
            const defs = svg.select('defs').empty()
                ? svg.append('defs') : svg.select('defs');
            const group = svg.append('g').attr('pointer-events', 'none');
            features.forEach((d, i) => {
                const clipId = this.uid + '-clip' + i;
                defs.append('clipPath').attr('id', clipId)
                    .append('path').attr('d', path(d));
                group.append('path')
                    .attr('d', path(d))
                    .attr('fill', 'none')
                    .attr('stroke', INK.brass).attr('stroke-width', 3)
                    .attr('clip-path', 'url(#' + clipId + ')');
            });
        }

        frame(featureCollection, ratio) {
            this.figure.innerHTML = '';
            const w = this.figure.clientWidth || (this.opts.small ? 640 : 960);
            const h = this.opts.height || Math.max(240, Math.round(w * ratio));
            const svg = d3.select(this.figure).append('svg')
                .attr('viewBox', [0, 0, w, h])
                .attr('width', '100%')
                .attr('role', 'img');
            const projection = this.depth === 'us'
                ? d3.geoAlbersUsa().fitExtent([[16, 16], [w - 16, h - 16]], featureCollection)
                : d3.geoAlbers().fitExtent([[16, 16], [w - 16, h - 16]], featureCollection);
            return { svg, w, h, path: d3.geoPath(projection) };
        }

        /* ── grid of named blocks (no shapes to draw) ──────────────── */

        renderGrid() {
            this.figure.innerHTML = '';
            const grid = el('div', 'gm-grid');
            const ramp = this.ramp();
            const units = (this.data.units || []).slice().sort((a, b) => {
                const an = parseInt(a.number, 10); const bn = parseInt(b.number, 10);
                if (!Number.isNaN(an) && !Number.isNaN(bn)) return an - bn;
                return a.name.localeCompare(b.name);
            });
            for (const row of units) {
                const cell = el('button', 'gm-cell');
                cell.type = 'button';
                const fillValue = this.lens === 'owned' ? row.owned : row.listed;
                cell.style.background = bucketColor(ramp, fillValue);
                cell.style.color = inkFor(bucketColor(ramp, fillValue));
                if (this.lens === 'owned' && !row.owned && row.listed) {
                    cell.classList.add('gm-cell--sale');
                }
                cell.textContent = row.name;
                cell.addEventListener('click', () => { if (!this.opts.small) this.select(row); });
                cell.addEventListener('pointermove', (event) => this.tipUnit(event, row));
                cell.addEventListener('pointerleave', () => this.hideTip());
                grid.appendChild(cell);
            }
            if (!units.length) {
                grid.appendChild(el('p', 'gm-fail',
                    'No units are on record for ' + esc(this.data.name) + ' yet.'));
            }
            this.figure.appendChild(grid);
            this.selGroup = null;
        }

        /* ── selection ─────────────────────────────────────────────── */

        select(row) {
            this.selection = row;
            if (this.selGroup && this.stateFC) {
                this.selGroup.selectAll('*').remove();
                const feature = this.stateFC.features
                    .find((d) => String(d.id) === row.fips);
                if (feature) {
                    /* Dark border plus a brass ring outside it (9f: Chosen).
                     * The wide brass stroke sits under the dark one. */
                    this.selGroup.append('path')
                        .attr('d', this.statePath(feature))
                        .attr('fill', 'none')
                        .attr('stroke', INK.brass).attr('stroke-width', 6);
                    this.selGroup.append('path')
                        .attr('d', this.statePath(feature))
                        .attr('fill', 'none')
                        .attr('stroke', INK.night).attr('stroke-width', 2);
                }
            }
            this.renderAside();
        }

        neighborsOf(row) {
            if (!this.neighborIndex || !row.fips) return [];
            const index = this.stateGeoms.findIndex((g) => String(g.id) === row.fips);
            if (index < 0) return [];
            const byFips = new Map(
                (this.data.units || []).filter((u) => u.fips).map((u) => [u.fips, u]));
            return this.neighborIndex[index]
                .map((i) => byFips.get(String(this.stateGeoms[i].id)))
                .filter(Boolean);
        }

        /* ── the aside: legend, then the panel is the click target ─── */

        renderAside() {
            if (!this.aside) return;
            this.aside.innerHTML = '';

            const legend = el('div', 'gm-legendcard');
            legend.appendChild(el('span', 'gm-lbl', 'How to read it'));
            const rampRows = this.ramp().slice().reverse();
            for (const [, color, label] of rampRows) {
                const rowEl = el('div', 'gm-legendrow');
                const swatch = el('span', 'gm-swatch');
                swatch.style.background = color;
                rowEl.appendChild(swatch);
                rowEl.appendChild(document.createTextNode(label));
                legend.appendChild(rowEl);
            }
            const mark = el('div', 'gm-legendrow');
            const markSwatch = el('span', 'gm-swatch');
            if (this.lens === 'listed') {
                markSwatch.style.background = '#f0ede6';
                markSwatch.style.boxShadow = 'inset 0 0 0 2px ' + INK.brass;
                mark.appendChild(markSwatch);
                mark.appendChild(document.createTextNode(
                    'A ' + this.unitWord() + ' you already hold'));
                if (this.opts.authed || this.opts.collector) legend.appendChild(mark);
            } else {
                markSwatch.className = 'gm-swatch gm-swatch--hatch';
                mark.appendChild(markSwatch);
                mark.appendChild(document.createTextNode('Something for sale'));
                legend.appendChild(mark);
            }
            this.aside.appendChild(legend);

            if (this.depth === 'us') this.usAsideCards();
            else this.unitAsideCards();
        }

        unitWord() {
            return this.depth === 'us' ? 'state'
                : ((this.data.unit_label || 'County')).toLowerCase();
        }

        usAsideCards() {
            const states = (this.data.states || []).filter((s) => s.active);
            const key = this.lens === 'owned' ? 'owned' : 'listed';
            const top = states.filter((s) => s[key] > 0)
                .sort((a, b) => b[key] - a[key]).slice(0, 8);
            if (!top.length) {
                this.aside.appendChild(el('p', 'gm-hint', this.lens === 'owned'
                    ? 'Nothing located yet — give a piece a state and it lands here.'
                    : 'Nothing is listed right now. The counties are still there.'));
                return;
            }
            const card = el('div', 'gm-card');
            card.appendChild(el('div', 'gm-card-h',
                '<b>' + (this.lens === 'owned' ? 'Where ' + (this.opts.collector ? 'they' : 'you') + ' collect' : 'Where the market is') + '</b>'
                + '<span>' + top.length + ' state' + (top.length === 1 ? '' : 's') + '</span>'));
            for (const s of top) {
                const rowEl = el('div', 'gm-card-r',
                    esc(s.name) + ' <span>' + s[key] + '</span>');
                card.appendChild(rowEl);
            }
            this.aside.appendChild(card);
        }

        unitAsideCards() {
            const row = this.selection;
            if (!row) {
                this.aside.appendChild(el('p', 'gm-hint',
                    'Click a ' + this.unitWord() + ' to open it — an empty one '
                    + 'still answers, with who collects it and a way to want it.'));
                return;
            }
            const links = this.opts.links;
            const card = el('div', 'gm-card');
            card.appendChild(el('div', 'gm-card-h',
                '<b>' + esc(row.name) + '</b><span>selected</span>'));

            const addRow = (label, value) => card.appendChild(
                el('div', 'gm-card-r', esc(label) + ' <span>' + value + '</span>'));

            if (this.lens === 'owned') {
                addRow('In the collection', row.owned || 0);
                if (row.owned_earliest) addRow('Earliest', row.owned_earliest);
                addRow('For sale today', row.listed
                    ? esc(String(row.listed)) : 'None');
                addRow('Held by others', row.collectors || 0);
            } else {
                addRow('Listed now', row.listed || 0);
                if (row.years) addRow('Years covered',
                    esc(row.years[0] + '–' + row.years[1]));
                if (this.opts.authed || this.opts.collector) {
                    addRow(this.opts.collector ? 'They hold' : 'You hold', row.owned || 0);
                }
            }

            const actions = el('div', 'gm-card-actions');
            if (row.listed && links.hunt) {
                const hunt = el('a', 'gm-btn gm-btn--dark', 'Hunt ' + esc(row.name));
                hunt.href = links.hunt + '?state_id=' + this.data.state_pk
                    + '&county_id=' + row.id;
                actions.appendChild(hunt);
            } else if (!row.listed && this.opts.authed && links.wantedCreate) {
                const want = el('a', 'gm-btn gm-btn--dark', 'Save a hunt for it');
                want.href = links.wantedCreate + '?state=' + this.data.state_pk
                    + '&county=' + row.id;
                actions.appendChild(want);
            }
            if (row.collectors && links.collectors) {
                const who = el('a', 'gm-cardlink',
                    row.collectors + ' collector' + (row.collectors === 1 ? '' : 's')
                    + ' here →');
                who.href = links.collectors + '?where=collect&state_id='
                    + this.data.state_pk + '&county_id=' + row.id;
                actions.appendChild(who);
            }
            const about = el('a', 'gm-cardlink', 'About ' + esc(row.name) + ' →');
            about.href = '/geographic-units/' + row.id + '/';
            actions.appendChild(about);
            card.appendChild(actions);
            this.aside.appendChild(card);

            if (this.lens === 'owned') this.gapsCard(row);
        }

        gapsCard(row) {
            const gaps = this.neighborsOf(row).filter((u) => !u.owned);
            if (!gaps.length || !this.data.gap_count) return;
            const card = el('div', 'gm-card');
            card.appendChild(el('div', 'gm-card-h',
                '<b>Nearest gaps</b><span>' + Math.min(gaps.length, 3) + ' of '
                + this.data.gap_count + '</span>'));
            for (const gap of gaps.slice(0, 3)) {
                const rowEl = el('div', 'gm-card-r gm-card-r--link',
                    esc(gap.name) + ' <span>'
                    + (gap.listed ? 'for sale' : '—') + '</span>');
                rowEl.addEventListener('click', () => this.select(gap));
                card.appendChild(rowEl);
            }
            this.aside.appendChild(card);
        }

        renderNote() {
            if (this.opts.small || this.depth !== 'state') {
                this.note.textContent = '';
                return;
            }
            const parts = [];
            if (this.data.statewide_listed) {
                parts.push(this.data.statewide_listed + ' listed statewide, tied to no '
                    + this.unitWord());
            }
            if (this.data.unplaced_listed) {
                parts.push(this.data.unplaced_listed + ' listed with no unit on record');
            }
            this.note.textContent = parts.length
                ? 'Off the map: ' + parts.join(' · ') + '.' : '';
        }

        /* ── tooltip: dark ground, three lines and a prompt, no arrow ─ */

        touchOnce(event, row) {
            /* On a touch screen the first tap shows the tooltip, the
             * second opens the county. */
            if (event.pointerType !== 'touch') return false;
            const key = row.fips || row.id;
            if (this.touchedKey === key) { this.touchedKey = null; return false; }
            this.touchedKey = key;
            this.tipUnit(event, row);
            return true;
        }

        tipUS(event, row) {
            if (!row) { this.hideTip(); return; }
            const lines = ['<b>' + esc(row.name) + '</b>'];
            if (!row.active) {
                lines.push('<span>No reference data yet</span>');
            } else {
                lines.push('<span>' + row.listed + ' listed</span>');
                if (row.owned) lines.push('<i>'
                    + (this.opts.collector ? 'They hold ' : 'You hold ')
                    + row.owned + ' from here</i>');
                if (!this.opts.small) lines.push('<u>Click to open it</u>');
            }
            this.showTip(event, lines.join(''));
        }

        tipUnit(event, row) {
            if (!row) { this.hideTip(); return; }
            /* "Lycoming County", but never "GMU 4 GMU". */
            const label = this.data.unit_label || '';
            const title = row.name.toLowerCase().includes(label.toLowerCase())
                ? row.name : (row.name + ' ' + label).trim();
            const lines = ['<b>' + esc(title) + '</b>'];
            const listedLine = row.listed
                ? row.listed + ' listed' + (row.years
                    ? ' · ' + row.years[0] + '–' + row.years[1] : '')
                : 'Nothing listed today';
            lines.push('<span>' + listedLine + '</span>');
            if (row.owned) {
                lines.push('<i>' + (this.opts.collector ? 'They hold ' : 'You hold ')
                    + row.owned + ' from here</i>');
            } else if (row.collectors) {
                lines.push('<i>' + row.collectors + ' collector'
                    + (row.collectors === 1 ? '' : 's') + ' here</i>');
            }
            if (!this.opts.small) lines.push('<u>Click to hunt it</u>');
            this.showTip(event, lines.join(''));
        }

        showTip(event, html) {
            this.tip.innerHTML = html;
            this.tip.style.display = 'block';
            /* Follows the cursor with a 12px offset and never crosses the
             * edge of the frame. */
            const pad = 12;
            const box = this.tip.getBoundingClientRect();
            let x = event.clientX + pad;
            let y = event.clientY + pad;
            if (x + box.width > window.innerWidth - 8) {
                x = event.clientX - box.width - pad;
            }
            if (y + box.height > window.innerHeight - 8) {
                y = event.clientY - box.height - pad;
            }
            this.tip.style.left = x + 'px';
            this.tip.style.top = y + 'px';
        }

        hideTip() {
            this.tip.style.display = 'none';
        }
    }

    window.GroundMap = GroundMap;
}());
