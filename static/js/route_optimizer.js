/**
 * Municipal Cleanup Truck Dispatch & 2-Opt TSP Route Optimizer
 */

window.RouteMap = null;
let routePolyline = null;
let routeMarkersGroup = null;

window.RouteOptimizer = {
  currentDepot: 'central',
  selectedClusterId: '',
  maxStops: 8,

  initMap: function() {
    const elem = document.getElementById('route-map');
    if (!elem || window.RouteMap) return;

    window.RouteMap = L.map('route-map', {
      center: [12.9716, 77.5946],
      zoom: 12,
      zoomControl: true
    });

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(window.RouteMap);

    routeMarkersGroup = L.layerGroup().addTo(window.RouteMap);
  },

  loadRoute: async function() {
    this.initMap();
    const depotSelect = document.getElementById('route-depot-select');
    const clusterSelect = document.getElementById('route-cluster-select');
    const stopsInput = document.getElementById('route-max-stops');

    if (depotSelect) this.currentDepot = depotSelect.value;
    if (clusterSelect) this.selectedClusterId = clusterSelect.value;
    if (stopsInput) this.maxStops = parseInt(stopsInput.value) || 8;

    const summaryBox = document.getElementById('route-summary-panel');
    if (summaryBox) {
      summaryBox.innerHTML = `
        <div class="p-6 text-center text-slate-500">
          <svg class="animate-spin h-6 w-6 text-emerald-600 mx-auto mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <p class="text-sm font-semibold">Running 2-Opt TSP Heuristic on Haversine Distance Matrix...</p>
        </div>
      `;
    }

    try {
      const params = new URLSearchParams({
        depot: this.currentDepot,
        cluster_id: this.selectedClusterId,
        max_stops: this.maxStops
      });

      const res = await fetch(`/api/route-optimizer?${params.toString()}`);
      const data = await res.json();
      if (!data.success) {
        showToast('Route calculation failed', 'error');
        return;
      }

      this.renderRouteMap(data);
      this.renderRouteItinerary(data);
    } catch (err) {
      console.error('Failed to optimize route:', err);
      showToast('Error calculating route', 'error');
    }
  },

  renderRouteMap: function(data) {
    if (!window.RouteMap || !routeMarkersGroup) return;

    routeMarkersGroup.clearLayers();
    if (routePolyline) window.RouteMap.removeLayer(routePolyline);

    const waypoints = data.waypoints || [];
    if (waypoints.length === 0) return;

    // Draw Animated Route Polyline
    const latlngs = data.polyline_coords || waypoints.map(w => [w.lat, w.lon]);
    routePolyline = L.polyline(latlngs, {
      color: '#10b981',
      weight: 5,
      opacity: 0.9,
      className: 'route-path-animated'
    }).addTo(window.RouteMap);

    // Add Stop Markers
    waypoints.forEach((wp, idx) => {
      const isDepot = wp.is_depot;
      const numLabel = isDepot ? 'HUB' : `#${wp.step_number - 1}`;
      const bgColor = isDepot ? '#0f172a' : '#10b981';

      const icon = L.divIcon({
        html: `
          <div style="
            background-color: ${bgColor};
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 9999px;
            border: 2px solid white;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            white-space: nowrap;
            text-align: center;
          ">
            ${numLabel} ${isDepot ? 'Depot' : ''}
          </div>
        `,
        className: 'route-step-pin',
        iconSize: [60, 24],
        iconAnchor: [30, 12]
      });

      const m = L.marker([wp.lat, wp.lon], { icon: icon });
      m.bindTooltip(`
        <strong>Step ${wp.step_number}: ${esc(wp.name)}</strong><br>
        ${wp.category ? 'Category: ' + esc(wp.category) : 'Municipal Dispatch Headquarters'}
      `);
      routeMarkersGroup.addLayer(m);
    });

    window.RouteMap.fitBounds(routePolyline.getBounds(), { padding: [40, 40] });
  },

  renderRouteItinerary: function(data) {
    const summaryBox = document.getElementById('route-summary-panel');
    const waypointsBox = document.getElementById('route-waypoints-list');
    if (!summaryBox || !waypointsBox) return;

    summaryBox.innerHTML = `
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <span class="text-xs text-slate-500 block">Total Distance</span>
          <span class="text-xl font-extrabold text-slate-900">${data.total_distance_km} km</span>
          <span class="text-[11px] text-emerald-600 block mt-0.5">-${data.efficiency_gain_percent}% vs random</span>
        </div>
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <span class="text-xs text-slate-500 block">Est. Time</span>
          <span class="text-xl font-extrabold text-slate-900">${data.estimated_duration_hours} hrs</span>
          <span class="text-[11px] text-slate-400 block mt-0.5">Driving + Loading</span>
        </div>
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <span class="text-xs text-slate-500 block">CO2 Saved</span>
          <span class="text-xl font-extrabold text-emerald-600">${data.co2_saved_kg} kg</span>
          <span class="text-[11px] text-slate-400 block mt-0.5">Fuel Optimization</span>
        </div>
        <div class="bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
          <span class="text-xs text-slate-500 block">Total Pickups</span>
          <span class="text-xl font-extrabold text-slate-900">${data.total_stops} dumps</span>
          <span class="text-[11px] text-slate-400 block mt-0.5">Round trip depot tour</span>
        </div>
      </div>
    `;

    waypointsBox.innerHTML = (data.waypoints || []).map((wp, idx) => {
      const isDepot = wp.is_depot;
      return `
        <div class="p-3 bg-white rounded-xl border border-slate-200 flex items-center space-x-3 text-xs">
          <div class="w-7 h-7 rounded-full flex items-center justify-center font-bold text-[10px] ${isDepot ? 'bg-slate-900 text-white' : 'bg-emerald-100 text-emerald-800'}">
            ${isDepot ? 'DEPOT' : idx}
          </div>
          <div class="flex-1">
            <h5 class="font-bold text-slate-800 text-sm leading-tight">${esc(wp.name)}</h5>
            <p class="text-slate-500 text-[11px]">${isDepot ? 'Start & Finish Logistics Depot' : 'Pickup Dump Site • ' + esc(wp.category || '')}</p>
          </div>
          ${!isDepot ? `
            <span class="bg-rose-50 text-rose-700 font-bold px-2 py-0.5 rounded text-[10px] border border-rose-200">
              Sev: ${wp.severity}/5
            </span>
          ` : ''}
        </div>
      `;
    }).join('');
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const calcBtn = document.getElementById('btn-recalculate-route');
  if (calcBtn) calcBtn.addEventListener('click', () => RouteOptimizer.loadRoute());

  const depotSel = document.getElementById('route-depot-select');
  if (depotSel) depotSel.addEventListener('change', () => RouteOptimizer.loadRoute());

  const clusterSel = document.getElementById('route-cluster-select');
  if (clusterSel) clusterSel.addEventListener('change', () => RouteOptimizer.loadRoute());
});
