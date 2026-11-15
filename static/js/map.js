/**
 * Leaflet Map Controller: Markers, Heatmap Layer, DBSCAN Hotspots, Ward Boundaries & Real GPS
 */

window.MainMap = null;

const MapLayers = {
  markerGroup: null,
  heatLayer: null,
  clusterGroup: null,
  wardGeoJsonLayer: null,
  userLocationMarker: null,
  userAccuracyCircle: null,
  heatmapEnabled: true,
  clustersEnabled: true,
  wardsEnabled: true,
  userLocation: null // { lat, lon, accuracy }
};

const BLR_CENTER = [12.9716, 77.5946];
const BLR_ZOOM = 12;

function initMainMap() {
  const mapElement = document.getElementById('main-map');
  if (!mapElement) return;

  window.MainMap = L.map('main-map', {
    center: BLR_CENTER,
    zoom: BLR_ZOOM,
    zoomControl: false
  });

  // Custom Zoom Control at Top Right
  L.control.zoom({ position: 'topright' }).addTo(window.MainMap);

  // Base map tiles (OpenStreetMap) with automatic fallback if tiles fail to load
  const osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(window.MainMap);

  let tileErrors = 0;
  osm.on('tileerror', () => {
    tileErrors++;
    if (tileErrors === 6) {
      console.warn('OSM tiles failing, switching to fallback tiles');
      window.MainMap.removeLayer(osm);
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 19
      }).addTo(window.MainMap);
    }
  });

  // Make sure Leaflet measures the container after layout settles
  setTimeout(() => window.MainMap.invalidateSize(), 300);
  window.addEventListener('load', () => window.MainMap.invalidateSize());
  window.addEventListener('resize', () => window.MainMap.invalidateSize());

  MapLayers.markerGroup = L.layerGroup().addTo(window.MainMap);
  MapLayers.clusterGroup = L.layerGroup().addTo(window.MainMap);

  loadWardBoundaries();
  refreshHotspots();
  setupMapControls();

  // Try auto-locating user on map start
  attemptUserLocation();
}

function attemptUserLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        updateUserLocationOnMap(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, false);
      },
      () => {},
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 }
    );
  }
}

// Locate Me Button Click
function locateUserOnMap() {
  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser', 'warning');
    return;
  }

  showToast('Acquiring real device GPS location...', 'info');

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const acc = Math.round(pos.coords.accuracy || 15);

      updateUserLocationOnMap(lat, lon, acc, true);
      if (isInsideBengaluru(lat, lon)) {
        showToast(`🎯 Real GPS Located: ±${acc}m accuracy`, 'success');
      } else {
        showToast('You appear to be outside Bengaluru. Reports are only shown for Bengaluru.', 'info');
      }

      // Re-render markers with distance calculations from user
      renderMarkers(AppState.reports);
    },
    (err) => {
      console.warn('Geolocation error:', err);
      showToast(gpsErrorMessage(err), 'warning');
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

function updateUserLocationOnMap(lat, lon, accuracy, flyTo = false) {
  MapLayers.userLocation = { lat, lon, accuracy };

  // Remove existing
  if (MapLayers.userLocationMarker) window.MainMap.removeLayer(MapLayers.userLocationMarker);
  if (MapLayers.userAccuracyCircle) window.MainMap.removeLayer(MapLayers.userAccuracyCircle);

  // Pulse Icon
  const userIcon = L.divIcon({
    html: `
      <div class="user-gps-container">
        <div class="user-gps-ring"></div>
        <div class="user-gps-dot"></div>
      </div>
    `,
    className: 'user-live-gps-pin',
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  MapLayers.userLocationMarker = L.marker([lat, lon], {
    icon: userIcon,
    zIndexOffset: 1000
  }).addTo(window.MainMap);

  MapLayers.userLocationMarker.bindTooltip('<strong>You Are Here</strong> (Real Device GPS)', {
    permanent: false,
    direction: 'top'
  });

  MapLayers.userAccuracyCircle = L.circle([lat, lon], {
    radius: accuracy,
    color: '#2563eb',
    weight: 1.5,
    fillColor: '#3b82f6',
    fillOpacity: 0.12
  }).addTo(window.MainMap);

  if (flyTo) {
    window.MainMap.flyTo([lat, lon], 15, { duration: 1.2 });
  }

  // Update Locate Button styling
  const locateBtn = document.getElementById('btn-map-locate-me');
  if (locateBtn) {
    locateBtn.classList.add('bg-blue-50', 'text-blue-700', 'border-blue-300');
  }
}

function setupMapControls() {
  const toggleHeat = document.getElementById('toggle-heat');
  const toggleClusters = document.getElementById('toggle-clusters');
  const toggleWards = document.getElementById('toggle-wards');
  const locateBtn = document.getElementById('btn-map-locate-me');

  if (locateBtn) {
    locateBtn.addEventListener('click', locateUserOnMap);
  }

  if (toggleHeat) {
    toggleHeat.addEventListener('change', (e) => {
      MapLayers.heatmapEnabled = e.target.checked;
      if (MapLayers.heatLayer) {
        if (e.target.checked) window.MainMap.addLayer(MapLayers.heatLayer);
        else window.MainMap.removeLayer(MapLayers.heatLayer);
      }
    });
  }

  if (toggleClusters) {
    toggleClusters.addEventListener('change', (e) => {
      MapLayers.clustersEnabled = e.target.checked;
      if (e.target.checked) window.MainMap.addLayer(MapLayers.clusterGroup);
      else window.MainMap.removeLayer(MapLayers.clusterGroup);
    });
  }

  if (toggleWards) {
    toggleWards.addEventListener('change', (e) => {
      MapLayers.wardsEnabled = e.target.checked;
      if (MapLayers.wardGeoJsonLayer) {
        if (e.target.checked) window.MainMap.addLayer(MapLayers.wardGeoJsonLayer);
        else window.MainMap.removeLayer(MapLayers.wardGeoJsonLayer);
      }
    });
  }
}

// Marker Icon Factory
function createCustomPin(status, priorityLevel) {
  let bgColor = '#ef4444'; // Red for Reported
  let symbol = '!';

  if (status === 'In Progress') {
    bgColor = '#f59e0b'; // Amber
    symbol = '•';
  } else if (status === 'Cleared') {
    bgColor = '#10b981'; // Emerald
    symbol = '✓';
  }

  const isCritical = priorityLevel === 'Critical' && status !== 'Cleared';
  const pulseClass = isCritical ? 'critical-hazard-pulse' : '';

  const html = `
    <div class="clean-map-pin ${pulseClass}" style="
      background-color: ${bgColor};
      width: 30px;
      height: 30px;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      border: 2px solid #ffffff;
      box-shadow: 0 4px 10px rgba(0,0,0,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
    ">
      <span style="
        transform: rotate(45deg);
        font-size: 13px;
        color: white;
        font-weight: 800;
        font-family: system-ui, sans-serif;
      ">${symbol}</span>
    </div>
  `;

  return L.divIcon({
    html: html,
    className: 'custom-map-pin',
    iconSize: [30, 30],
    iconAnchor: [15, 30],
    popupAnchor: [0, -30]
  });
}

// Render Report Markers on Map
function renderMarkers(reports) {
  if (!MapLayers.markerGroup) return;
  MapLayers.markerGroup.clearLayers();

  reports.forEach(report => {
    if (!report.latitude || !report.longitude) return;

    const icon = createCustomPin(report.status, report.priority_level);
    const marker = L.marker([report.latitude, report.longitude], { icon: icon });

    marker.bindPopup(() => createReportPopupHTML(report), {
      maxWidth: 320,
      className: 'custom-report-popup'
    });

    MapLayers.markerGroup.addLayer(marker);
  });
}

// Generate Rich Popup HTML
function createReportPopupHTML(report) {
  const statusColors = {
    'Reported': 'bg-rose-50 text-rose-700 border-rose-200',
    'In Progress': 'bg-amber-50 text-amber-700 border-amber-200',
    'Cleared': 'bg-emerald-50 text-emerald-700 border-emerald-200'
  };

  const priorityColors = {
    'Critical': 'bg-rose-600 text-white',
    'High': 'bg-orange-500 text-white',
    'Medium': 'bg-amber-500 text-white',
    'Low': 'bg-emerald-600 text-white'
  };

  const materials = Array.isArray(report.ai_materials) ? report.ai_materials : [];
  const materialsPills = materials.slice(0, 3).map(m => `<span class="bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md text-[10px] font-semibold">${esc(m)}</span>`).join(' ');

  // Compute distance from user GPS if available
  let distText = '';
  if (MapLayers.userLocation) {
    const d = calculateHaversine(
      MapLayers.userLocation.lat,
      MapLayers.userLocation.lon,
      report.latitude,
      report.longitude
    );
    distText = d < 1000 ? `${Math.round(d)}m away from you` : `${(d / 1000).toFixed(1)} km away from you`;
  }

  return `
    <div class="p-3.5 font-sans text-slate-800 w-72">
      <div class="relative rounded-xl overflow-hidden mb-2.5 bg-slate-100 border border-slate-200 shadow-xs">
        <img src="${esc(report.image_url)}" alt="Waste Photo" class="w-full h-32 object-cover" />
        <span class="absolute top-2 left-2 text-[10px] font-extrabold px-2 py-0.5 rounded-full ${priorityColors[report.priority_level] || 'bg-slate-600 text-white'} shadow-sm">
          ${report.priority_level} (${Math.round(report.priority_score)}/100)
        </span>
        <span class="absolute top-2 right-2 text-[10px] font-bold px-2 py-0.5 rounded-full border ${statusColors[report.status]} shadow-xs">
          ${report.status}
        </span>
      </div>

      <div class="mb-1">
        <span class="text-[11px] font-bold text-emerald-700 uppercase tracking-wider">${esc(report.category)}</span>
        <h4 class="font-bold text-sm text-slate-900 leading-snug">${esc(report.title)}</h4>
      </div>

      <p class="text-xs text-slate-500 mb-2 truncate">${esc(report.address || report.ward_name)}</p>

      ${distText ? `
        <div class="flex items-center space-x-1.5 text-[11px] font-bold text-blue-600 bg-blue-50/80 px-2 py-1 rounded-md mb-2">
          <span>${distText}</span>
        </div>
      ` : ''}

      ${materials.length > 0 ? `<div class="flex flex-wrap gap-1 mb-2">${materialsPills}</div>` : ''}

      ${report.closest_receptor_name ? `
        <div class="bg-indigo-50/70 border border-indigo-100 rounded-lg p-2 mb-2.5 text-[11px] text-indigo-900">
          <strong>Eco Receptor:</strong> ${Math.round(report.closest_receptor_dist)}m to <em>${esc(report.closest_receptor_name)}</em>
        </div>
      ` : ''}

      <div class="flex items-center justify-between pt-2.5 border-t border-slate-100">
        <button onclick="handleUpvote('${esc(report.id)}')" class="flex items-center space-x-1.5 text-xs font-bold px-3 py-1.5 bg-slate-50 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 rounded-xl transition-all border border-slate-200 shadow-xs">
          <span id="popup-upvote-${report.id}">${report.upvotes || 0} Upvotes</span>
        </button>

        <button onclick="openAdminModal('${esc(report.id)}')" class="text-xs font-bold text-slate-600 hover:text-slate-900 underline">
          Admin Action →
        </button>
      </div>
    </div>
  `;
}

// Distance Helper (Haversine in meters)
function calculateHaversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Handle Upvote
async function handleUpvote(reportId) {
  try {
    const res = await fetch(`/api/reports/${reportId}/upvote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.success) {
      showToast('Thank you for verifying this dump! Priority increased.', 'success');
      const elem = document.getElementById(`popup-upvote-${reportId}`);
      if (elem) elem.innerText = `${data.new_upvotes} Upvotes`;
      fetchReports();
    } else {
      showToast(data.message || 'Already upvoted', 'warning');
    }
  } catch (err) {
    showToast('Failed to record upvote', 'error');
  }
}

// Load and Render Heatmap & DBSCAN Hotspots
async function refreshHotspots() {
  try {
    const res = await fetch('/api/hotspots');
    const data = await res.json();
    if (!data.success) return;

    // 1. Render Heatmap Layer
    if (window.L && L.heatLayer && data.heatmap_points) {
      if (MapLayers.heatLayer) {
        window.MainMap.removeLayer(MapLayers.heatLayer);
      }
      try {
        MapLayers.heatLayer = L.heatLayer(data.heatmap_points, {
          radius: 26,
          blur: 18,
          maxZoom: 16,
          gradient: { 0.2: '#22c55e', 0.5: '#eab308', 0.8: '#f97316', 1.0: '#ef4444' }
        });
        if (MapLayers.heatmapEnabled) {
          MapLayers.heatLayer.addTo(window.MainMap);
        }
      } catch (heatErr) {
        console.warn('Heatmap could not be drawn:', heatErr);
      }
    }

    // 2. Render DBSCAN Cluster Polygons & Labels
    MapLayers.clusterGroup.clearLayers();
    const rankedHotspotsContainer = document.getElementById('ranked-hotspots-list');
    if (rankedHotspotsContainer) rankedHotspotsContainer.innerHTML = '';

    data.clusters.forEach((cluster, idx) => {
      const circle = L.circle([cluster.center.lat, cluster.center.lon], {
        radius: cluster.radius_m + 30,
        color: '#dc2626',
        weight: 2,
        fillColor: '#ef4444',
        fillOpacity: 0.12,
        dashArray: '5, 5'
      });

      circle.bindTooltip(`
        <div class="font-sans text-xs">
          <strong>${esc(cluster.name)}</strong><br>
          Reports: ${cluster.total_reports} | Open: ${cluster.open_reports}<br>
          Dumping Severity Index: <strong>${cluster.dumping_index}</strong>
        </div>
      `, { sticky: true });

      MapLayers.clusterGroup.addLayer(circle);

      // Populate Top Hotspots Sidebar List
      if (rankedHotspotsContainer && idx < 6) {
        const item = document.createElement('div');
        item.className = 'p-3 bg-white/95 rounded-2xl border border-slate-200/90 hover:border-rose-400 hover:shadow-md transition-all cursor-pointer shadow-xs';
        item.innerHTML = `
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[10px] font-extrabold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
              #${idx + 1} Recurring Hotspot
            </span>
            <span class="text-xs font-mono font-bold text-slate-700">Index: ${cluster.dumping_index}</span>
          </div>
          <h5 class="text-sm font-bold text-slate-900">${esc(cluster.primary_ward)}</h5>
          <p class="text-xs text-slate-500 mb-2">Dominant: <strong>${esc(cluster.primary_category)}</strong> (${cluster.total_reports} reports)</p>
          <div class="flex items-center justify-between text-xs font-medium">
            <span class="text-slate-600">🚨 Open: <strong>${cluster.open_reports}</strong></span>
            <button class="text-emerald-600 hover:text-emerald-700 font-bold" onclick="focusCluster(${cluster.center.lat}, ${cluster.center.lon})">
              Focus &rarr;
            </button>
          </div>
        `;
        rankedHotspotsContainer.appendChild(item);
      }
    });
  } catch (err) {
    console.error('Failed to load hotspots:', err);
  }
}

function focusCluster(lat, lon) {
  if (window.MainMap) {
    window.MainMap.setView([lat, lon], 15, { animate: true });
    switchTab('map-view');
  }
}

// Load Ward Boundaries GeoJSON
async function loadWardBoundaries() {
  try {
    const res = await fetch('/api/wards');
    const data = await res.json();
    if (!data.success) return;

    if (MapLayers.wardGeoJsonLayer) {
      window.MainMap.removeLayer(MapLayers.wardGeoJsonLayer);
    }

    MapLayers.wardGeoJsonLayer = L.geoJSON(data.geojson, {
      style: (feature) => {
        const rate = feature.properties.clearance_rate || 50;
        let color = '#22c55e';
        if (rate < 30) color = '#ef4444';
        else if (rate < 60) color = '#f97316';
        else if (rate < 80) color = '#eab308';

        return {
          color: color,
          weight: 2,
          opacity: 0.8,
          fillColor: color,
          fillOpacity: 0.10
        };
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties;
        layer.bindTooltip(`
          <div class="font-sans text-xs">
            <strong>${esc(props.ward_name)}</strong> (${esc(props.ward_id)})<br>
            Total Dumps: ${props.total_reports || 0} | Open: ${props.open_reports || 0}<br>
            Clearance Rate: ${props.clearance_rate || 0}% | Grade: ${props.grade || 'N/A'}
          </div>
        `, { sticky: true });

        layer.on({
          mouseover: (e) => {
            const l = e.target;
            l.setStyle({ weight: 3, fillOpacity: 0.22 });
          },
          mouseout: (e) => {
            MapLayers.wardGeoJsonLayer.resetStyle(e.target);
          },
          click: (e) => {
            window.MainMap.fitBounds(e.target.getBounds());
            showToast(`Focused on ${esc(props.ward_name)}`, 'info');
          }
        });
      }
    });

    if (MapLayers.wardsEnabled) {
      MapLayers.wardGeoJsonLayer.addTo(window.MainMap);
    }
  } catch (err) {
    console.error('Failed to load wards GeoJSON:', err);
  }
}

document.addEventListener('DOMContentLoaded', initMainMap);
