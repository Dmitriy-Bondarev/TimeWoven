/**
 * Family Graph v2 - TimeWoven
 *
 * UX contract:
 *   click person    -> focus (dim others) + update bottom panel
 *   click union     -> update bottom panel with union info
 *   right-click     -> set as graph root (reload)
 *   hover person    -> lightweight name tooltip
 *   <- / ->         -> focus history navigation
 *   depth - / +     -> reload graph with new depth
 *   filter buttons  -> show/hide partner edges, child edges, deceased
 */
(function () {
  'use strict';

  const CURRENT_YEAR = new Date().getFullYear();
  const YEAR_MIN = 1900;
  const YEAR_MAX = CURRENT_YEAR + 5;
  const USE_STABLE_UPDATE = true; // Prototype 6C.2 flag: in-place graph updates for year mode.
  const initialYear = Number.isInteger(window.GRAPH_YEAR) ? window.GRAPH_YEAR : null;

  const state = {
    rootPersonId: window.GRAPH_ROOT_PERSON_ID || 1,
    depth: Math.max(1, Math.min(10, window.GRAPH_DEPTH || 2)),
    focusedPersonId: window.GRAPH_ROOT_PERSON_ID || 1,
    focusHistory: [window.GRAPH_ROOT_PERSON_ID || 1],
    focusHistoryIndex: 0,
    filters: { partner: true, child: true, deceased: true },
    selectedUnionId: null,
    temporalMode: initialYear ? 'year' : 'now',
    selectedYear: normalizeYear(initialYear || CURRENT_YEAR),
    activeYear: null,
    hoveredNodeId: null,
    keyframes: [],
    currentKeyframeIndex: -1,
    keyframeModeEnabled: false,
    lastRenderedKeyframeYear: null,
    wheelNavLocked: false,
  };

  const MIN_DEPTH = 1;
  const MAX_DEPTH = 10;

  const container = document.getElementById('graph');
  const tooltipEl = document.getElementById('graph-tooltip');
  const infoPanelEl = document.getElementById('graph-info-panel');
  const focusNameEl = document.getElementById('focus-name');
  const depthEl = document.getElementById('depth-display');
  const btnBack = document.getElementById('btn-back');
  const btnFwd = document.getElementById('btn-forward');
  const btnDec = document.getElementById('btn-depth-dec');
  const btnInc = document.getElementById('btn-depth-inc');
  const btnModeNow = document.getElementById('btn-mode-now');
  const btnModeYear = document.getElementById('btn-mode-year');
  const yearInput = document.getElementById('year-input');
  const yearSlider = document.getElementById('year-slider');
  const btnKeyframePrev = document.getElementById('btn-keyframe-prev');
  const btnKeyframeNext = document.getElementById('btn-keyframe-next');
  const btnKeyframeMode = document.getElementById('btn-keyframe-mode');
  const keyframeYearEl = document.getElementById('keyframe-year');
  const keyframeNavEl = document.getElementById('keyframe-nav');
  const graphWrapperEl = document.getElementById('graph-wrapper');
  if (!container) return;

  let svg;
  let zoomBehavior;
  let g;
  let edgeLayer;
  let nodeLayer;
  let simulation;
  let nodeEls;
  let edgeEls;
  let currentNodes = [];
  let currentLinks = [];
  let requestSequence = 0;
  let keyframeYearFlashTimer = null;
  const debouncedApplyYearAndReload = debounce((year) => applyYearAndReloadGraph(year), 250);

  setupControls();
  loadAndRender(state.rootPersonId, state.depth);

  async function loadAndRender(rootId, depth, options = {}) {
    const requestedYear = getRequestedYear();
    const requestId = ++requestSequence;
    try {
      const params = new URLSearchParams({
        root_person_id: String(rootId),
        depth: String(depth),
      });
      if (requestedYear !== null) params.set('year', String(requestedYear));

      const res = await fetch(`/family/tree/json?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Ignore stale responses from older requests when rapid keyframe/year navigation is in progress.
      if (requestId !== requestSequence) return;

      state.activeYear = requestedYear;

      const nextNodes = data.nodes.map((n) => ({ ...n }));
      const nextLinks = data.edges.map((e) => ({ ...e }));
      refreshKeyframes(nextNodes, nextLinks);

      if (canUseStableUpdate(options)) {
        applyStableSnapshot(nextNodes, nextLinks);
        return;
      }

      currentNodes = nextNodes;
      currentLinks = nextLinks;
    } catch (err) {
      if (requestId !== requestSequence) return;
      container.innerHTML = `<p style="color:red;padding:20px">Ошибка загрузки: ${err.message}</p>`;
      return;
    }
    render();
  }

  function setupControls() {
    if (depthEl) depthEl.textContent = String(state.depth);
    if (yearInput) {
      yearInput.min = String(YEAR_MIN);
      yearInput.max = String(YEAR_MAX);
    }
    if (yearSlider) {
      yearSlider.min = String(YEAR_MIN);
      yearSlider.max = String(YEAR_MAX);
      yearSlider.step = '1';
    }
    setYearInUI(state.selectedYear);

    if (btnBack) {
      btnBack.addEventListener('click', () => {
        if (state.focusHistoryIndex <= 0) return;
        state.focusHistoryIndex -= 1;
        state.focusedPersonId = state.focusHistory[state.focusHistoryIndex];
        updateHistoryButtons();
        updateVisuals(true);
        updateFocusLabel();
        const node = currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId);
        updateBottomPanel(node || null);
      });
    }

    if (btnFwd) {
      btnFwd.addEventListener('click', () => {
        if (state.focusHistoryIndex >= state.focusHistory.length - 1) return;
        state.focusHistoryIndex += 1;
        state.focusedPersonId = state.focusHistory[state.focusHistoryIndex];
        updateHistoryButtons();
        updateVisuals(true);
        updateFocusLabel();
        const node = currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId);
        updateBottomPanel(node || null);
      });
    }

    if (btnDec) {
      btnDec.addEventListener('click', () => {
        if (state.depth <= MIN_DEPTH) return;
        state.depth -= 1;
        if (depthEl) depthEl.textContent = String(state.depth);
        updateDepthButtons();
        loadAndRender(state.rootPersonId, state.depth);
      });
    }

    if (btnInc) {
      btnInc.addEventListener('click', () => {
        if (state.depth >= MAX_DEPTH) return;
        state.depth += 1;
        if (depthEl) depthEl.textContent = String(state.depth);
        updateDepthButtons();
        loadAndRender(state.rootPersonId, state.depth);
      });
    }

    if (btnModeNow) {
      btnModeNow.addEventListener('click', () => {
        if (state.temporalMode === 'now') return;
        state.temporalMode = 'now';
        setYearInUI(CURRENT_YEAR);
        updateTemporalControls();
        loadAndRender(state.rootPersonId, state.depth);
      });
    }

    if (btnModeYear) {
      btnModeYear.addEventListener('click', () => {
        if (state.temporalMode === 'year') return;
        state.temporalMode = 'year';
        if (!isValidYear(state.selectedYear)) state.selectedYear = CURRENT_YEAR;
        syncKeyframeIndexFromSelectedYear();
        setYearInUI(state.selectedYear);
        updateTemporalControls();
        loadAndRender(state.rootPersonId, state.depth);
      });
    }

    if (yearInput) {
      yearInput.addEventListener('change', () => {
        const val = getCurrentYearFromUI();
        if (!isValidYear(val)) {
          setYearInUI(state.selectedYear);
          return;
        }
        applyYearAndReloadGraph(val);
      });

      yearInput.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Enter') return;
        const val = getCurrentYearFromUI();
        if (!isValidYear(val)) {
          setYearInUI(state.selectedYear);
          return;
        }
        state.selectedYear = val;
        setYearInUI(state.selectedYear);
        if (state.temporalMode !== 'year') {
          state.temporalMode = 'year';
          updateTemporalControls();
        }
        applyYearAndReloadGraph(state.selectedYear);
      });
    }

    if (yearSlider) {
      yearSlider.addEventListener('input', () => {
        const val = parseInt(yearSlider.value, 10);
        if (!isValidYear(val)) return;
        state.selectedYear = normalizeYear(val);
        setYearInUI(val);
        if (state.temporalMode === 'year') debouncedApplyYearAndReload(val);
      });

      yearSlider.addEventListener('change', () => {
        const val = parseInt(yearSlider.value, 10);
        if (!isValidYear(val)) return;
        state.selectedYear = normalizeYear(val);
        setYearInUI(val);
        if (state.temporalMode === 'year') applyYearAndReloadGraph(val);
      });
    }

    if (btnKeyframePrev) {
      btnKeyframePrev.addEventListener('click', () => {
        goToPrevKeyframe();
      });
    }

    if (btnKeyframeNext) {
      btnKeyframeNext.addEventListener('click', () => {
        goToNextKeyframe();
      });
    }

    if (btnKeyframeMode) {
      btnKeyframeMode.addEventListener('click', () => {
        state.keyframeModeEnabled = !state.keyframeModeEnabled;
        updateKeyframeModeControls();
      });
    }

    if (graphWrapperEl) {
      graphWrapperEl.addEventListener('wheel', onWheelKeyframeNavigate, { passive: false });
    }
    if (keyframeNavEl) {
      keyframeNavEl.addEventListener('wheel', onWheelKeyframeNavigate, { passive: false });
    }

    document.querySelectorAll('.ctrl-btn[data-filter]').forEach((btn) => {
      const key = btn.dataset.filter;
      if (!key || !(key in state.filters)) return;
      btn.classList.toggle('active', !!state.filters[key]);
      btn.addEventListener('click', () => {
        state.filters[key] = !state.filters[key];
        btn.classList.toggle('active', !!state.filters[key]);
        updateVisuals(true);
      });
    });

    updateDepthButtons();
    updateHistoryButtons();
    updateFocusLabel();
    updateTemporalControls();
    updateKeyframeControls();
    updateKeyframeModeControls();
  }

  function render() {
    container.innerHTML = '';
    hideTooltip();
    const width = container.clientWidth || 1200;
    const height = container.clientHeight || 700;

    svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

    const defs = svg.append('defs');
    ['partner', 'child'].forEach((t) => {
      defs.append('marker')
        .attr('id', `arr-${t}`)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('refX', 8)
        .attr('refY', 3)
        .attr('orient', 'auto')
        .append('polygon')
        .attr('points', '0 0, 8 3, 0 6')
        .attr('fill', t === 'partner' ? '#4a90e2' : '#22c55e');
    });

    g = svg.append('g');
    zoomBehavior = d3.zoom().scaleExtent([0.15, 5]).on('zoom', (ev) => g.attr('transform', ev.transform));
    zoomBehavior.filter((ev) => shouldAllowZoomEvent(ev));
    svg.call(zoomBehavior);
    svg.on('click.bg', hideTooltip);

    edgeLayer = g.append('g');
    nodeLayer = g.append('g');

    const rootNode =
      currentNodes.find((n) => n.type === 'person' && n.person_id === state.rootPersonId) ||
      currentNodes.find((n) => n.type === 'person');
    if (rootNode) {
      rootNode.fx = width / 2;
      rootNode.fy = height / 2;
    }

    if (!currentNodes.find((n) => n.person_id === state.focusedPersonId)) {
      state.focusedPersonId = rootNode ? rootNode.person_id : null;
    }

    simulation = d3
      .forceSimulation(currentNodes)
      .force('link', d3.forceLink(currentLinks).id((d) => d.id).distance((d) => {
        const srcPid = d.source && typeof d.source === 'object' ? d.source.person_id : null;
        const tgtPid = d.target && typeof d.target === 'object' ? d.target.person_id : null;
        const isRootEdge = srcPid === state.rootPersonId || tgtPid === state.rootPersonId;
        const base = d.type === 'child' ? 130 : 95;
        return isRootEdge ? base + 28 : base;
      }))
      .force('charge', d3.forceManyBody().strength(-420))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide((d) => {
        if (d.type === 'union') return 16;
        return d.person_id === state.rootPersonId ? 50 : 44;
      }))
      .on('tick', tick)
      .on('end', () => centerOn(rootNode, width, height));

    edgeEls = edgeLayer
      .selectAll('line')
      .data(currentLinks, (d) => d.id)
      .enter()
      .append('line')
      .attr('class', (d) => `edge edge-${d.type}`)
      .attr('stroke', (d) => edgeStroke(d))
      .attr('stroke-width', (d) => edgeWidth(d))
      .attr('stroke-dasharray', (d) => edgeDash(d))
      .attr('marker-end', (d) => `url(#arr-${d.type})`);

    nodeEls = nodeLayer
      .selectAll('g.node')
      .data(currentNodes, (d) => d.id)
      .enter()
      .append('g')
      .attr('class', (d) => `node node-${d.type}`)
      .call(
        d3
          .drag()
          .on('start', (ev, d) => {
            if (!ev.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (ev, d) => {
            d.fx = ev.x;
            d.fy = ev.y;
          })
          .on('end', (ev, d) => {
            if (!ev.active) simulation.alphaTarget(0);
            if (d.person_id !== state.focusedPersonId) {
              d.fx = null;
              d.fy = null;
            }
          })
      );

    nodeEls
      .append('circle')
      .attr('class', 'focus-ring')
      .attr('r', (d) => nodeRadius(d) + 7)
      .attr('fill', 'none')
      .attr('stroke', '#f0b14f')
      .attr('stroke-width', 2.5)
      .attr('opacity', 0);

    nodeEls
      .append('circle')
      .attr('class', 'node-circle')
      .attr('r', (d) => nodeRadius(d))
      .attr('fill', (d) => nodeFill(d))
      .attr('stroke', '#f8fafc')
      .attr('stroke-width', 1.6)
      .attr('cursor', (d) => (d.type === 'person' ? 'pointer' : 'default'));

    nodeEls
      .filter((d) => d.type === 'person')
      .append('text')
      .attr('class', 'node-name')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => nodeRadius(d) + 14)
      .attr('font-size', '11px')
      .attr('fill', '#2f3a45')
      .attr('pointer-events', 'none')
      .text((d) => personLabel(d));

    nodeEls
      .filter((d) => d.type === 'union')
      .append('text')
      .attr('class', 'node-union')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '8px')
      .attr('fill', (d) => unionLabelFill(d))
      .attr('pointer-events', 'none')
      .text('\u222a');

    nodeEls
      .on('click', (ev, d) => {
        ev.stopPropagation();
        if (d.type === 'person') {
          state.selectedUnionId = null;
          setFocus(d.person_id);
          updateBottomPanel(d);
        } else if (d.type === 'union') {
          state.selectedUnionId = d.id;
          updateBottomPanel(d);
          updateVisuals();
        }
      })
      .on('contextmenu', (ev, d) => {
        ev.preventDefault();
        if (d.type !== 'person') return;
        hideTooltip();
        reroot(d.person_id);
      });

    nodeEls
      .on('mouseenter.hover', (ev, d) => {
        state.hoveredNodeId = d.id;
        updateVisuals(true);
      })
      .on('mouseleave.hover', () => {
        state.hoveredNodeId = null;
        updateVisuals(true);
      })
      .filter((d) => d.type === 'person')
      .on('mouseenter', (ev, d) => showTooltip(ev, d))
      .on('mouseleave', () => hideTooltip());

    updateVisuals();
    updateFocusLabel();
    updateHistoryButtons();
    updateKeyframeControls();

    const initNode = currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId);
    updateBottomPanel(initNode || null);
  }

  function setFocus(personId) {
    if (personId === state.focusedPersonId) return;
    state.focusHistory = state.focusHistory.slice(0, state.focusHistoryIndex + 1);
    state.focusHistory.push(personId);
    state.focusHistoryIndex = state.focusHistory.length - 1;
    state.focusedPersonId = personId;
    updateHistoryButtons();
    updateVisuals(true);
    updateFocusLabel();
  }

  function reroot(personId) {
    state.rootPersonId = personId;
    state.focusedPersonId = personId;
    state.focusHistory = [personId];
    state.focusHistoryIndex = 0;
    updateHistoryButtons();
    loadAndRender(personId, state.depth);
  }

  function canUseStableUpdate(options) {
    if (!USE_STABLE_UPDATE) return false;
    if (!options || options.stable !== true) return false;
    if (state.temporalMode !== 'year') return false;
    return !!(svg && simulation && edgeLayer && nodeLayer);
  }

  function applyStableSnapshot(nextNodes, nextLinks) {
    const width = container.clientWidth || 1200;
    const height = container.clientHeight || 700;
    const previousNodeById = new Map(currentNodes.map((n) => [n.id, n]));
    const previousRoot = previousNodeById.get(`p_${state.rootPersonId}`);

    currentNodes = nextNodes.map((node) => {
      const previous = previousNodeById.get(node.id);
      if (previous) {
        return {
          ...previous,
          ...node,
          x: previous.x,
          y: previous.y,
          vx: previous.vx,
          vy: previous.vy,
          fx: previous.fx,
          fy: previous.fy,
        };
      }

      const baseX = previousRoot && Number.isFinite(previousRoot.x) ? previousRoot.x : width / 2;
      const baseY = previousRoot && Number.isFinite(previousRoot.y) ? previousRoot.y : height / 2;
      return {
        ...node,
        x: baseX + (Math.random() - 0.5) * 36,
        y: baseY + (Math.random() - 0.5) * 36,
        vx: 0,
        vy: 0,
      };
    });

    currentLinks = nextLinks.map((edge) => {
      const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
      const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
      return {
        ...edge,
        source: sourceId,
        target: targetId,
      };
    });

    edgeEls = edgeLayer
      .selectAll('line')
      .data(currentLinks, (d) => d.id)
      .join(
        (enter) => enter
          .append('line')
          .attr('class', (d) => `edge edge-${d.type}`)
          .attr('stroke', (d) => edgeStroke(d))
          .attr('stroke-width', (d) => edgeWidth(d))
          .attr('stroke-dasharray', (d) => edgeDash(d))
          .attr('marker-end', (d) => `url(#arr-${d.type})`)
          .attr('opacity', 0)
          .call((sel) => sel.transition().duration(220).attr('opacity', 1)),
        (update) => update,
        (exit) => exit.call((sel) => sel.transition().duration(220).attr('opacity', 0).remove())
      )
      .attr('class', (d) => `edge edge-${d.type}`)
      .attr('stroke', (d) => edgeStroke(d))
      .attr('stroke-width', (d) => edgeWidth(d))
      .attr('stroke-dasharray', (d) => edgeDash(d))
      .attr('marker-end', (d) => `url(#arr-${d.type})`);

    const enteringNodes = nodeLayer
      .selectAll('g.node')
      .data(currentNodes, (d) => d.id)
      .join(
        (enter) => {
          const group = enter
            .append('g')
            .attr('class', (d) => `node node-${d.type}`)
            .attr('opacity', 0)
            .call(
              d3
                .drag()
                .on('start', (ev, d) => {
                  if (!ev.active) simulation.alphaTarget(0.3).restart();
                  d.fx = d.x;
                  d.fy = d.y;
                })
                .on('drag', (ev, d) => {
                  d.fx = ev.x;
                  d.fy = ev.y;
                })
                .on('end', (ev, d) => {
                  if (!ev.active) simulation.alphaTarget(0);
                  if (d.person_id !== state.focusedPersonId) {
                    d.fx = null;
                    d.fy = null;
                  }
                })
            );

          group
            .append('circle')
            .attr('class', 'focus-ring')
            .attr('r', (d) => nodeRadius(d) + 7)
            .attr('fill', 'none')
            .attr('stroke', '#f0b14f')
            .attr('stroke-width', 2.5)
            .attr('opacity', 0);

          group
            .append('circle')
            .attr('class', 'node-circle')
            .attr('r', (d) => nodeRadius(d))
            .attr('fill', (d) => nodeFill(d))
            .attr('stroke', '#f8fafc')
            .attr('stroke-width', 1.6)
            .attr('cursor', (d) => (d.type === 'person' ? 'pointer' : 'default'));

          group
            .filter((d) => d.type === 'person')
            .append('text')
            .attr('class', 'node-name')
            .attr('text-anchor', 'middle')
            .attr('dy', (d) => nodeRadius(d) + 14)
            .attr('font-size', '11px')
            .attr('fill', '#2f3a45')
            .attr('pointer-events', 'none')
            .text((d) => personLabel(d));

          group
            .filter((d) => d.type === 'union')
            .append('text')
            .attr('class', 'node-union')
            .attr('text-anchor', 'middle')
            .attr('dy', '0.35em')
            .attr('font-size', '8px')
            .attr('fill', (d) => unionLabelFill(d))
            .attr('pointer-events', 'none')
            .text('\u222a');

          return group.call((sel) => sel.transition().duration(220).attr('opacity', 1));
        },
        (update) => update,
        (exit) => exit.call((sel) => sel.transition().duration(220).attr('opacity', 0).remove())
      );

    nodeEls = enteringNodes.attr('class', (d) => `node node-${d.type}`);
    attachNodeInteractions(nodeEls);

    nodeEls
      .select('.focus-ring')
      .attr('r', (d) => nodeRadius(d) + 7)
      .attr('opacity', (d) => (d.person_id === state.focusedPersonId ? 1 : 0));

    nodeEls
      .select('.node-circle')
      .attr('r', (d) => nodeRadius(d))
      .attr('fill', (d) => nodeFill(d));

    nodeEls
      .select('.node-name')
      .attr('dy', (d) => nodeRadius(d) + 14)
      .text((d) => personLabel(d));

    nodeEls
      .select('.node-union')
      .attr('fill', (d) => unionLabelFill(d))
      .attr('opacity', (d) => (isUnionInactiveForYear(d) ? 0.62 : 1));

    const linkForce = simulation.force('link');
    simulation.nodes(currentNodes);
    if (linkForce) linkForce.links(currentLinks);
    simulation.alpha(0.28).restart();

    if (!currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId)) {
      const fallback = currentNodes.find((n) => n.type === 'person' && n.person_id === state.rootPersonId)
        || currentNodes.find((n) => n.type === 'person');
      state.focusedPersonId = fallback ? fallback.person_id : null;
    }

    updateVisuals(true);
    updateFocusLabel();
    updateHistoryButtons();
    updateKeyframeControls();

    const node = currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId);
    updateBottomPanel(node || null);
  }

  function attachNodeInteractions(selection) {
    selection
      .on('click', (ev, d) => {
        ev.stopPropagation();
        if (d.type === 'person') {
          state.selectedUnionId = null;
          setFocus(d.person_id);
          updateBottomPanel(d);
        } else if (d.type === 'union') {
          state.selectedUnionId = d.id;
          updateBottomPanel(d);
          updateVisuals();
        }
      })
      .on('contextmenu', (ev, d) => {
        ev.preventDefault();
        if (d.type !== 'person') return;
        hideTooltip();
        reroot(d.person_id);
      });

    selection
      .on('mouseenter.hover', (ev, d) => {
        state.hoveredNodeId = d.id;
        updateVisuals(true);
      })
      .on('mouseleave.hover', () => {
        state.hoveredNodeId = null;
        updateVisuals(true);
      });

    selection
      .filter((d) => d.type === 'person')
      .on('mouseenter', (ev, d) => showTooltip(ev, d))
      .on('mouseleave', () => hideTooltip());
  }

  function updateVisuals(animated) {
    if (!nodeEls || !edgeEls) return;
    const dur = animated ? 220 : 0;
    const connected = neighbors(state.focusedPersonId);
    const tr = (sel) => (animated ? sel.transition().duration(dur) : sel);
    const focusedNodeId = `p_${state.focusedPersonId}`;

    const hiddenNodeIds = new Set();
    currentNodes.forEach((n) => {
      if (!state.filters.deceased && n.type === 'person' && n.is_alive === false) {
        hiddenNodeIds.add(n.id);
      }
    });

    const visibleEdgeIds = new Set();
    currentLinks.forEach((e) => {
      if (!state.filters.partner && e.type === 'partner') return;
      if (!state.filters.child && e.type === 'child') return;
      const s = nid(e.source);
      const t = nid(e.target);
      if (hiddenNodeIds.has(s) || hiddenNodeIds.has(t)) return;
      visibleEdgeIds.add(e.id);
    });

    const visibleDegree = new Map();
    currentNodes.forEach((n) => visibleDegree.set(n.id, 0));
    currentLinks.forEach((e) => {
      if (!visibleEdgeIds.has(e.id)) return;
      const s = nid(e.source);
      const t = nid(e.target);
      visibleDegree.set(s, (visibleDegree.get(s) || 0) + 1);
      visibleDegree.set(t, (visibleDegree.get(t) || 0) + 1);
    });

    currentNodes.forEach((n) => {
      if (n.id === focusedNodeId) return;
      if ((visibleDegree.get(n.id) || 0) === 0) hiddenNodeIds.add(n.id);
    });
    hiddenNodeIds.delete(focusedNodeId);

    tr(nodeEls.select('.focus-ring')).attr('opacity', (d) => (d.person_id === state.focusedPersonId ? 1 : 0));

    tr(nodeEls.select('.node-circle'))
      .attr('opacity', (d) => {
        if (hiddenNodeIds.has(d.id)) return 0;
        return nodeOpacity(d, connected);
      })
      .attr('stroke-width', (d) => {
        if (d.person_id === state.focusedPersonId) return 3;
        if (d.type === 'union' && d.id === state.selectedUnionId) return 2.5;
        if (d.id === state.hoveredNodeId) return 2.1;
        return 1.5;
      })
      .attr('stroke', (d) => {
        if (d.type === 'union' && d.id === state.selectedUnionId) return '#f0b14f';
        if (d.id === state.hoveredNodeId) return '#dce3ea';
        return '#f8fafc';
      })
      .attr('fill', (d) => nodeFill(d))
      .attr('r', (d) => nodeRadius(d));

    tr(nodeEls.select('.node-name'))
      .attr('opacity', (d) => {
        if (hiddenNodeIds.has(d.id)) return 0;
        if (d.person_id === state.focusedPersonId) return 1;
        if (d.id === state.hoveredNodeId) return 0.96;
        return connected.has(d.id) ? 0.75 : 0.1;
      })
      .attr('dy', (d) => nodeRadius(d) + 14)
      .text((d) => personLabel(d));

    tr(nodeEls.select('.node-union'))
      .attr('fill', (d) => unionLabelFill(d))
      .attr('opacity', (d) => (isUnionInactiveForYear(d) ? 0.62 : 1));

    tr(edgeEls)
      .attr('opacity', (e) => {
        if (!visibleEdgeIds.has(e.id)) return 0;
        const s = nid(e.source);
        const t = nid(e.target);
        const fp = focusedNodeId;
        const temporalOpacity = edgeTemporalOpacity(e);
        if (s === fp || t === fp) return Math.max(0.25, Math.min(1, temporalOpacity + 0.15));
        if (connected.has(s) && connected.has(t)) return Math.max(0.2, temporalOpacity);
        return Math.max(0.06, temporalOpacity * 0.2);
      })
      .attr('stroke', (e) => edgeStroke(e))
      .attr('stroke-width', (e) => edgeWidth(e))
      .attr('stroke-dasharray', (e) => edgeDash(e));

    // Apply hard visibility at the end so no later updates overwrite it.
    nodeEls.style('display', (d) => (hiddenNodeIds.has(d.id) ? 'none' : null));
    nodeEls.select('.node-name').style('display', (d) => (hiddenNodeIds.has(d.id) ? 'none' : null));
    nodeEls.select('.node-union').style('display', (d) => (hiddenNodeIds.has(d.id) ? 'none' : null));
    edgeEls.style('display', (e) => (visibleEdgeIds.has(e.id) ? null : 'none'));
  }

  function neighbors(personId) {
    const pid = `p_${personId}`;
    const set = new Set([pid]);
    currentLinks.forEach((e) => {
      const s = nid(e.source);
      const t = nid(e.target);
      if (s === pid) set.add(t);
      if (t === pid) set.add(s);
    });
    currentLinks.forEach((e) => {
      const s = nid(e.source);
      const t = nid(e.target);
      if (set.has(s)) set.add(t);
      if (set.has(t)) set.add(s);
    });
    return set;
  }

  function nodeOpacity(d, connected) {
    if (!state.filters.deceased && d.is_alive === false) return 0;
    if (d.id === state.hoveredNodeId) return 1;
    if (d.type === 'union') {
      if (isUnionInactiveForYear(d)) return connected.has(d.id) ? 0.46 : 0.12;
      return connected.has(d.id) ? 0.72 : 0.16;
    }
    if (d.person_id === state.focusedPersonId) return 1;
    const base = d.is_alive === false ? 0.56 : 0.88;
    return connected.has(d.id) ? base : 0.12;
  }

  function showTooltip(ev, d) {
    if (!tooltipEl) return;
    const label = d.display_name || d.name || 'Персона';
    tooltipEl.textContent = label;

    const rect = container.getBoundingClientRect();
    let tx = ev.clientX - rect.left + 14;
    let ty = ev.clientY - rect.top - 28;
    tooltipEl.style.display = 'block';
    const tw = tooltipEl.offsetWidth || 140;
    if (tx + tw > container.clientWidth - 4) tx = container.clientWidth - tw - 4;
    if (ty < 4) ty = 4;
    tooltipEl.style.left = `${tx}px`;
    tooltipEl.style.top = `${ty}px`;
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.style.display = 'none';
  }

  function updateBottomPanel(node) {
    if (!infoPanelEl) return;
    const contentEl = infoPanelEl.querySelector('.gip-content');
    const placeholderEl = infoPanelEl.querySelector('.gip-placeholder');
    const nameEl = infoPanelEl.querySelector('.gip-name');
    const metaEl = infoPanelEl.querySelector('.gip-meta');
    const actionsEl = infoPanelEl.querySelector('.gip-actions');

    if (!node) {
      if (contentEl) contentEl.style.display = 'none';
      if (placeholderEl) placeholderEl.style.display = '';
      return;
    }

    if (contentEl) contentEl.style.display = '';
    if (placeholderEl) placeholderEl.style.display = 'none';

    if (node.type === 'person') {
      nameEl.textContent = node.display_name || node.name || 'Персона';

      const sections = [];
      sections.push(sectionHtml('Годы жизни', formatLifeYears(node)));
      if (node.gender === 'male') sections.push(sectionHtml('Пол', 'мужской'));
      if (node.gender === 'female') sections.push(sectionHtml('Пол', 'женский'));
      if (!node.gender || (node.gender !== 'male' && node.gender !== 'female')) {
        sections.push(sectionHtml('Пол', 'не указан'));
      }

      const unions = getPersonUnions(node.person_id);
      if (unions.length > 0) {
        const unionText = unions
          .map((u) => `${u.partners || 'Союз'} (${formatPeriod(u.unionNode.start_date, u.unionNode.end_date)})`)
          .join('; ');
        sections.push(sectionHtml('Союзы', unionText));
      } else {
        sections.push(sectionHtml('Союзы', 'нет данных'));
      }

      sections.push(`<div class="gip-section gip-temporal">${esc(buildTemporalSummaryForPerson(node.person_id))}</div>`);
      metaEl.innerHTML = sections.join('');

      const profileBtn = node.url
        ? `<button class="gip-btn gip-primary" data-action="profile" data-url="${esc(node.url)}">Перейти в профиль</button>`
        : '';
      const rootBtn = `<button class="gip-btn gip-secondary" data-action="root" data-pid="${node.person_id}">Сделать корнем</button>`;
      const timelineBtn = `<button class="gip-btn gip-secondary" data-action="timeline-person" data-pid="${node.person_id}">Timeline человека</button>`;
      actionsEl.innerHTML = profileBtn + rootBtn + timelineBtn;

      actionsEl.querySelectorAll('.gip-btn').forEach((btn) => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          if (btn.dataset.action === 'profile') window.location.href = btn.dataset.url;
          else if (btn.dataset.action === 'root') reroot(parseInt(btn.dataset.pid, 10));
          else if (btn.dataset.action === 'timeline-person') {
            window.location.href = `/family/timeline?person_id=${encodeURIComponent(btn.dataset.pid)}`;
          }
        });
      });
    } else if (node.type === 'union') {
      const partners = getUnionPartners(node.id);
      const partnerNames = partners.map((p) => p.name || p.display_name || '?').join(' + ');
      const children = getUnionChildren(node.id);
      const childrenText = children.length
        ? children.map((c) => c.name || c.display_name || '?').join(', ')
        : 'нет данных';

      nameEl.textContent = partnerNames ? `Союз: ${partnerNames}` : 'Союз';
      const statusText = node.is_active === true ? 'активен' : (node.is_active === false ? 'завершён' : 'неизвестно');
      metaEl.innerHTML = [
        sectionHtml('Партнёры', partnerNames || 'нет данных'),
        sectionHtml('Период', formatPeriod(node.start_date, node.end_date)),
        sectionHtml('Статус', statusText),
        sectionHtml('Дети', childrenText),
      ].join('');

      const unionId = parseUnionNumericId(node.id);
      if (unionId !== null) {
        actionsEl.innerHTML = `<button class="gip-btn gip-secondary" data-action="timeline-union" data-uid="${unionId}">Timeline союза</button>`;
        actionsEl.querySelectorAll('.gip-btn').forEach((btn) => {
          btn.addEventListener('click', (ev) => {
            ev.stopPropagation();
            if (btn.dataset.action === 'timeline-union') {
              window.location.href = `/family/timeline?union_id=${encodeURIComponent(btn.dataset.uid)}`;
            }
          });
        });
      } else {
        actionsEl.innerHTML = '';
      }
    }
  }

  function getUnionPartners(unionNodeId) {
    return currentLinks
      .filter((e) => (nid(e.source) === unionNodeId || nid(e.target) === unionNodeId) && e.type === 'partner')
      .map((e) => {
        const otherId = nid(e.source) === unionNodeId ? nid(e.target) : nid(e.source);
        return currentNodes.find((n) => n.id === otherId);
      })
      .filter(Boolean);
  }

  function getUnionChildren(unionNodeId) {
    return currentLinks
      .filter((e) => nid(e.source) === unionNodeId && e.type === 'child')
      .map((e) => currentNodes.find((n) => n.id === nid(e.target)))
      .filter(Boolean);
  }

  function getPersonUnions(personId) {
    const personNodeId = `p_${personId}`;
    return currentLinks
      .filter((e) => e.type === 'partner' && (nid(e.source) === personNodeId || nid(e.target) === personNodeId))
      .map((e) => {
        const unionNodeId = nid(e.source) === personNodeId ? nid(e.target) : nid(e.source);
        const unionNode = currentNodes.find((n) => n.id === unionNodeId && n.type === 'union');
        if (!unionNode) return null;
        const partners = getUnionPartners(unionNodeId)
          .map((p) => p.name || p.display_name || '?')
          .join(' + ');
        return { unionNode, partners, edge: e };
      })
      .filter(Boolean);
  }

  function buildTemporalSummaryForPerson(personId) {
    const personNodeId = `p_${personId}`;
    const rel = currentLinks.filter(
      (e) => e.type === 'partner' && (nid(e.source) === personNodeId || nid(e.target) === personNodeId)
    );
    if (!rel.length) return 'Temporal: нет союзов';

    let active = 0;
    let inactive = 0;
    let neutral = 0;
    rel.forEach((e) => {
      if (e.is_active_for_year === true) active += 1;
      else if (e.is_active_for_year === false) inactive += 1;
      else neutral += 1;
    });

    const yearLabel = state.activeYear !== null ? String(state.activeYear) : String(CURRENT_YEAR);
    return `Состояние на ${yearLabel} год: активных ${active}, завершённых ${inactive}, нейтральных ${neutral}`;
  }

  function updateDepthButtons() {
    if (btnDec) btnDec.disabled = state.depth <= MIN_DEPTH;
    if (btnInc) btnInc.disabled = state.depth >= MAX_DEPTH;
  }

  function updateHistoryButtons() {
    if (btnBack) {
      const disabled = state.focusHistoryIndex <= 0;
      btnBack.disabled = disabled;
      btnBack.title = disabled ? 'Нет предыдущего фокуса' : 'Назад по истории фокуса';
    }
    if (btnFwd) {
      const disabled = state.focusHistoryIndex >= state.focusHistory.length - 1;
      btnFwd.disabled = disabled;
      btnFwd.title = disabled ? 'Нет следующего фокуса' : 'Вперёд по истории фокуса';
    }
  }

  function updateFocusLabel() {
    if (!focusNameEl) return;
    const node = currentNodes.find((n) => n.type === 'person' && n.person_id === state.focusedPersonId);
    focusNameEl.textContent = node ? node.name || `#${state.focusedPersonId}` : '-';
  }

  function updateTemporalControls() {
    if (btnModeNow) btnModeNow.classList.toggle('active', state.temporalMode === 'now');
    if (btnModeYear) btnModeYear.classList.toggle('active', state.temporalMode === 'year');
    if (yearInput) yearInput.disabled = state.temporalMode !== 'year';
    if (yearSlider) yearSlider.disabled = state.temporalMode !== 'year';
    updateKeyframeControls();
    updateKeyframeModeControls();
  }

  function updateKeyframeControls() {
    const hasKeyframes = state.keyframes.length > 0;
    const isYearMode = state.temporalMode === 'year';
    const isEnabled = hasKeyframes && isYearMode;
    const idx = state.currentKeyframeIndex;

    if (btnKeyframePrev) btnKeyframePrev.disabled = !isEnabled || idx <= 0;
    if (btnKeyframeNext) btnKeyframeNext.disabled = !isEnabled || idx < 0 || idx >= state.keyframes.length - 1;

    if (keyframeYearEl) {
      let labelYear = null;
      if (!hasKeyframes) {
        keyframeYearEl.textContent = 'Кадр: —';
      } else if (idx >= 0 && idx < state.keyframes.length) {
        labelYear = state.keyframes[idx];
        keyframeYearEl.textContent = `Кадр: ${labelYear}`;
      } else {
        labelYear = state.keyframes[0];
        keyframeYearEl.textContent = `Кадр: ${labelYear}`;
      }

      if (labelYear !== state.lastRenderedKeyframeYear) {
        state.lastRenderedKeyframeYear = labelYear;
        flashKeyframeYear();
      }
    }
  }

  function updateKeyframeModeControls() {
    const isYearMode = state.temporalMode === 'year';
    const enabled = isYearMode && state.keyframeModeEnabled;
    if (btnKeyframeMode) {
      btnKeyframeMode.classList.toggle('active', enabled);
      btnKeyframeMode.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      btnKeyframeMode.title = enabled
        ? 'Слои времени включены: колесо листает keyframes'
        : 'Слои времени выключены: колесо масштабирует граф';
      btnKeyframeMode.textContent = enabled ? 'Слои времени: ON' : 'Слои времени: OFF';
    }
    if (keyframeNavEl) keyframeNavEl.classList.toggle('keyframe-mode-on', enabled);
  }

  function shouldAllowZoomEvent(ev) {
    const event = ev || {};
    if (event.type === 'wheel' && state.temporalMode === 'year' && state.keyframeModeEnabled) {
      return false;
    }
    return (!event.ctrlKey || event.type === 'wheel') && !event.button;
  }

  function flashKeyframeYear() {
    if (!keyframeYearEl) return;
    keyframeYearEl.classList.remove('is-flash');
    // Force reflow so repeated year updates retrigger the highlight.
    void keyframeYearEl.offsetWidth;
    keyframeYearEl.classList.add('is-flash');
    if (keyframeYearFlashTimer) clearTimeout(keyframeYearFlashTimer);
    keyframeYearFlashTimer = setTimeout(() => {
      keyframeYearEl.classList.remove('is-flash');
    }, 220);
  }

  function tick() {
    edgeEls
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y);
    nodeEls.attr('transform', (d) => `translate(${d.x},${d.y})`);
  }

  function centerOn(node, width, height) {
    if (!node) return;
    svg
      .transition()
      .duration(600)
      .call(zoomBehavior.transform, d3.zoomIdentity.translate(width / 2 - node.x, height / 2 - node.y));
  }

  function nodeRadius(d) {
    if (d.type === 'union') return 7;
    return d.person_id === state.focusedPersonId ? 32 : 21;
  }

  function nodeFill(d) {
    if (d.type === 'union') {
      if (isUnionInactiveForYear(d)) return '#b7c1cb';
      return '#6f7b86';
    }
    if (d.gender === 'male') return '#5f86aa';
    if (d.gender === 'female') return '#b97a8d';
    return '#8e99a5';
  }

  function isUnionInactiveForYear(node) {
    if (!node || node.type !== 'union' || state.temporalMode !== 'year') return false;
    const active = typeof node.is_active_for_year !== 'undefined' && node.is_active_for_year !== null
      ? node.is_active_for_year
      : node.is_active;
    return active === false;
  }

  function unionLabelFill(node) {
    return isUnionInactiveForYear(node) ? '#d8dee6' : '#f8fafc';
  }

  function getRequestedYear() {
    if (state.temporalMode === 'year') return isValidYear(state.selectedYear) ? state.selectedYear : CURRENT_YEAR;
    return null;
  }

  function getCurrentYearFromUI() {
    if (!yearInput) return null;
    const val = parseInt(yearInput.value, 10);
    return Number.isInteger(val) ? val : null;
  }

  function setYearInUI(year) {
    const normalized = normalizeYear(year);
    if (yearInput) yearInput.value = String(normalized);
    if (yearSlider) yearSlider.value = String(normalized);
  }

  function applyYearAndReloadGraph(year) {
    if (!isValidYear(year)) return;
    const normalized = normalizeYear(year);
    state.selectedYear = normalized;
    syncKeyframeIndexFromSelectedYear();
    setYearInUI(normalized);
    if (state.temporalMode !== 'year') return;
    loadAndRender(state.rootPersonId, state.depth, { stable: true });
  }

  function buildKeyframesFromGraphData(nodes, edges) {
    const years = new Set();

    nodes.forEach((node) => {
      addYearCandidate(years, node.birth_year);
      addYearCandidate(years, node.death_year);
      addYearCandidate(years, node.birth_date);
      addYearCandidate(years, node.death_date);
      if (node.type === 'union') {
        addYearCandidate(years, node.start_date);
        addYearCandidate(years, node.end_date);
      }
    });

    edges.forEach((edge) => {
      addYearCandidate(years, edge.start_date);
      addYearCandidate(years, edge.end_date);
      addYearCandidate(years, edge.valid_from);
      addYearCandidate(years, edge.valid_to);
    });

    return Array.from(years).sort((a, b) => a - b);
  }

  function refreshKeyframes(nodes, edges) {
    const prevYear = state.selectedYear;
    state.keyframes = buildKeyframesFromGraphData(nodes, edges);

    if (!state.keyframes.length) {
      state.currentKeyframeIndex = -1;
      updateKeyframeControls();
      return;
    }

    const exactIdx = state.keyframes.indexOf(prevYear);
    if (exactIdx >= 0) {
      state.currentKeyframeIndex = exactIdx;
    } else {
      state.currentKeyframeIndex = nearestKeyframeIndex(prevYear);
    }
    updateKeyframeControls();
  }

  function syncKeyframeIndexFromSelectedYear() {
    if (!state.keyframes.length) {
      state.currentKeyframeIndex = -1;
      updateKeyframeControls();
      return;
    }
    const exactIdx = state.keyframes.indexOf(state.selectedYear);
    state.currentKeyframeIndex = exactIdx >= 0 ? exactIdx : nearestKeyframeIndex(state.selectedYear);
    updateKeyframeControls();
  }

  function nearestKeyframeIndex(year) {
    if (!state.keyframes.length) return -1;
    let bestIdx = 0;
    let bestDist = Infinity;
    state.keyframes.forEach((y, idx) => {
      const dist = Math.abs(y - year);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = idx;
      }
    });
    return bestIdx;
  }

  function goToNextKeyframe() {
    if (state.temporalMode !== 'year') return;
    if (!state.keyframes.length) return;
    if (state.currentKeyframeIndex < 0) {
      state.currentKeyframeIndex = nearestKeyframeIndex(state.selectedYear);
    }
    if (state.currentKeyframeIndex >= state.keyframes.length - 1) return;
    const target = state.keyframes[state.currentKeyframeIndex + 1];
    applyYearAndReloadGraph(target);
  }

  function goToPrevKeyframe() {
    if (state.temporalMode !== 'year') return;
    if (!state.keyframes.length) return;
    if (state.currentKeyframeIndex < 0) {
      state.currentKeyframeIndex = nearestKeyframeIndex(state.selectedYear);
    }
    if (state.currentKeyframeIndex <= 0) return;
    const target = state.keyframes[state.currentKeyframeIndex - 1];
    applyYearAndReloadGraph(target);
  }

  function onWheelKeyframeNavigate(ev) {
    if (!state.keyframeModeEnabled) return;
    if (state.temporalMode !== 'year') return;
    if (!state.keyframes.length) return;
    if (!ev || typeof ev.deltaY !== 'number') return;

    ev.preventDefault();
    ev.stopPropagation();
    if (state.wheelNavLocked) return;
    state.wheelNavLocked = true;
    setTimeout(() => {
      state.wheelNavLocked = false;
    }, 260);

    if (ev.deltaY > 0) goToNextKeyframe();
    else if (ev.deltaY < 0) goToPrevKeyframe();
  }

  function addYearCandidate(targetSet, raw) {
    const year = extractYearValue(raw);
    if (year === null) return;
    if (!isValidYear(year)) return;
    targetSet.add(year);
  }

  function extractYearValue(raw) {
    if (raw === null || typeof raw === 'undefined') return null;
    if (Number.isInteger(raw)) return raw;
    if (typeof raw === 'number' && Number.isFinite(raw)) return Math.trunc(raw);
    if (typeof raw !== 'string') return null;

    const value = raw.trim();
    if (!value) return null;

    if (/^\d{4}$/.test(value)) return parseInt(value, 10);

    const dotted = value.match(/(?:^|\D)(\d{4})$/);
    if (dotted) return parseInt(dotted[1], 10);

    const anyYear = value.match(/(\d{4})/);
    if (anyYear) return parseInt(anyYear[1], 10);

    return null;
  }

  function isValidYear(value) {
    return Number.isInteger(value) && value >= YEAR_MIN && value <= YEAR_MAX;
  }

  function normalizeYear(value) {
    const num = Number.isInteger(value) ? value : CURRENT_YEAR;
    return Math.max(YEAR_MIN, Math.min(YEAR_MAX, num));
  }

  function debounce(fn, delay) {
    let timer = null;
    return function debounced(...args) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function edgeStroke(edge) {
    if (edge.is_active_for_year === false) return '#c7ced6';
    if (edge.is_active_for_year === null || typeof edge.is_active_for_year === 'undefined') {
      return edge.type === 'partner' ? '#8099b2' : '#85a894';
    }
    return edge.type === 'partner' ? '#3f7cc3' : '#34a26b';
  }

  function edgeWidth(edge) {
    if (edge.is_active_for_year === false) return edge.type === 'partner' ? 1.9 : 1.7;
    if (edge.is_active_for_year === null || typeof edge.is_active_for_year === 'undefined') {
      return edge.type === 'partner' ? 2.15 : 1.95;
    }
    return edge.type === 'partner' ? 2.9 : 2.4;
  }

  function edgeDash(edge) {
    if (edge.is_active_for_year === false) return edge.type === 'child' ? '5 5' : '4 6';
    if (edge.type === 'child') return '7 3';
    return null;
  }

  function edgeTemporalOpacity(edge) {
    if (edge.is_active_for_year === true) return 0.96;
    if (edge.is_active_for_year === false) return 0.3;
    return 0.62;
  }

  function formatLifeYears(node) {
    const by = node.birth_year || '?';
    const dy = node.death_year || (node.is_alive === false ? '?' : '...');
    return `${by} - ${dy}`;
  }

  function formatPeriod(startDate, endDate) {
    const s = startDate || '?';
    const e = endDate || '...';
    return `${s} - ${e}`;
  }

  function parseUnionNumericId(unionNodeId) {
    if (!unionNodeId || typeof unionNodeId !== 'string') return null;
    const m = unionNodeId.match(/^u_(\d+)$/);
    return m ? parseInt(m[1], 10) : null;
  }

  function firstName(name) {
    return (name.trim().split(/\s+/)[0] || '').substring(0, 12);
  }

  function personLabel(node) {
    const rawName = node.display_name || node.name || 'Персона';
    if (node.person_id === state.focusedPersonId) {
      return `${clip(rawName, 18)} (${formatLifeYears(node)})`;
    }
    return firstName(rawName);
  }

  function sectionHtml(label, value) {
    return `<div class="gip-section"><span class="gip-key">${esc(label)}:</span>${esc(value)}</div>`;
  }

  function clip(text, maxLen) {
    const s = String(text || '').trim();
    if (s.length <= maxLen) return s;
    return `${s.slice(0, maxLen - 3)}...`;
  }

  function nid(nodeOrId) {
    return typeof nodeOrId === 'object' ? nodeOrId.id : nodeOrId;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
})();
