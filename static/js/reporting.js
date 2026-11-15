/**
 * Citizen Waste Reporting & Real GPS Auto-Mapping Controller
 */

window.PickerMap = null;
let pickerMarker = null;
let pickerAccuracyCircle = null;

const ReportingState = {
  currentLat: 12.9716,
  currentLon: 77.5946,
  userRealGPS: null,
  isRealGPSActive: false,
  selectedFile: null,
  aiResult: null,
  isAnalyzing: false,
  pendingDuplicateInfo: null,
  isReverseGeocoding: false
};

// Preset GPS hubs for fast testing/demo
const GPS_PRESETS = {
  indiranagar: { name: 'Indiranagar 100ft Road', lat: 12.9782, lon: 77.6435, ward: 'Domlur & Indiranagar' },
  bellandur: { name: 'Bellandur Lake Canal Road', lat: 12.9360, lon: 77.6740, ward: 'Bellandur (Catchment)' },
  koramangala: { name: 'Koramangala 80ft Road', lat: 12.9340, lon: 77.6250, ward: 'Koramangala' },
  peenya: { name: 'Peenya Industrial 4th Cross', lat: 13.0280, lon: 77.5210, ward: 'Peenya Industrial Area' },
  whitefield: { name: 'Whitefield ITPL Main Road', lat: 12.9750, lon: 77.7450, ward: 'Whitefield & Kadugodi' },
  hsr: { name: 'HSR Layout Sector 2', lat: 12.9120, lon: 77.6420, ward: 'HSR Layout' }
};

function initPickerMap() {
  const container = document.getElementById('picker-map');
  if (!container || window.PickerMap) return;

  window.PickerMap = L.map('picker-map', {
    center: [ReportingState.currentLat, ReportingState.currentLon],
    zoom: 14,
    zoomControl: true
  });

  // Clean CartoDB Voyager Map Tiles
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(window.PickerMap);

  // Custom Sleek Map Pin
  const customIcon = L.divIcon({
    html: `
      <div class="clean-map-pin" style="
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
        width: 36px;
        height: 36px;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        border: 2.5px solid #ffffff;
        box-shadow: 0 8px 18px rgba(220, 38, 38, 0.45);
        display: flex;
        align-items: center;
        justify-content: center;
      ">
        <span style="transform: rotate(45deg); font-size: 14px; font-weight: bold; color: white;">!</span>
      </div>
    `,
    className: 'picker-pin-wrapper',
    iconSize: [36, 36],
    iconAnchor: [18, 36]
  });

  pickerMarker = L.marker([ReportingState.currentLat, ReportingState.currentLon], {
    icon: customIcon,
    draggable: true
  }).addTo(window.PickerMap);

  pickerMarker.on('dragend', (e) => {
    const pos = e.target.getLatLng();
    setCoordinates(pos.lat, pos.lng, false);
  });

  window.PickerMap.on('click', (e) => {
    pickerMarker.setLatLng(e.latlng);
    setCoordinates(e.latlng.lat, e.latlng.lng, false);
  });

  // Auto-attempt real device GPS on initialization
  attemptAutoGPS();
}

// Auto attempt GPS on load
function attemptAutoGPS() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        const acc = Math.round(pos.coords.accuracy || 15);
        if (!isInsideBengaluru(lat, lon)) {
          showToast('Your location is outside Bengaluru. Tap the map to place the pin manually.', 'info');
          return;
        }
        ReportingState.userRealGPS = { lat, lon, acc };
        setCoordinates(lat, lon, true, acc);
        // Without this the pin moved but the map stayed where it was, so the location looked missing
        if (window.PickerMap) window.PickerMap.setView([lat, lon], 16);
      },
      (err) => {
        console.log('Auto GPS unavailable:', err && err.message);
        if (!window.isSecureContext) showToast(gpsErrorMessage(err), 'warning');
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 }
    );
  }
}

// Acquire Live Device GPS
function triggerRealGPS() {
  if (!navigator.geolocation) {
    showToast('Geolocation is not supported by your browser', 'warning');
    return;
  }

  const gpsBadge = document.getElementById('gps-status-pill');
  if (gpsBadge) {
    gpsBadge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 animate-pulse';
    gpsBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-500 animate-ping"></span><span>Locking Real GPS Satellites...</span>`;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const accuracy = Math.round(pos.coords.accuracy || 10);

      if (!isInsideBengaluru(lat, lon)) {
        showToast('Your location is outside Bengaluru. Tap the map to place the pin manually.', 'warning');
        if (gpsBadge) {
          gpsBadge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200';
          gpsBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-400"></span><span>Pinpoint GPS Mode</span>`;
        }
        return;
      }

      const addrEl = document.getElementById('report-address');
      if (addrEl) delete addrEl.dataset.userEdited;   // fresh GPS fix: refresh the address too
      ReportingState.userRealGPS = { lat, lon, accuracy };
      setCoordinates(lat, lon, true, accuracy);

      if (window.PickerMap) {
        window.PickerMap.flyTo([lat, lon], 16, { duration: 1.2 });
      }

      showToast(`🎯 Real GPS Locked: ±${accuracy}m accuracy`, 'success');
    },
    (err) => {
      console.warn('Real GPS access failed or denied:', err);
      showToast(gpsErrorMessage(err), 'warning');
      if (gpsBadge) {
        gpsBadge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200';
        gpsBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-400"></span><span>Pinpoint GPS Mode</span>`;
      }
    },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
  );
}

// Apply GPS Preset Hub
function applyGPSPreset(presetKey) {
  const p = GPS_PRESETS[presetKey];
  if (!p) return;

  setCoordinates(p.lat, p.lon, false, null);
  if (window.PickerMap) {
    window.PickerMap.flyTo([p.lat, p.lon], 16, { duration: 1.0 });
  }

  const addressInput = document.getElementById('report-address');
  const wardSelect = document.getElementById('report-ward');
  if (addressInput) { delete addressInput.dataset.userEdited; addressInput.value = p.name + ', Bengaluru'; }
  if (wardSelect) wardSelect.value = p.ward;

  showToast(`Moved to ${p.name}`, 'info');
}

// Coordinate updates with Reverse Geocoding
async function setCoordinates(lat, lon, isRealGPS = false, accuracy = null) {
  ReportingState.currentLat = parseFloat(lat.toFixed(6));
  ReportingState.currentLon = parseFloat(lon.toFixed(6));
  ReportingState.isRealGPSActive = isRealGPS;

  // Update inputs
  const latInput = document.getElementById('report-lat');
  const lonInput = document.getElementById('report-lon');
  const coordDisplay = document.getElementById('coord-display');
  const gpsBadge = document.getElementById('gps-status-pill');

  if (latInput) latInput.value = ReportingState.currentLat;
  if (lonInput) lonInput.value = ReportingState.currentLon;
  if (coordDisplay) coordDisplay.innerText = `${ReportingState.currentLat}, ${ReportingState.currentLon}`;

  // Update Status Pill
  if (gpsBadge) {
    if (isRealGPS) {
      gpsBadge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200';
      gpsBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span>Real GPS Locked (±${accuracy || 10}m)</span>`;
    } else {
      gpsBadge.className = 'flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200';
      gpsBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-blue-500"></span><span>Pinpoint Location</span>`;
    }
  }

  // Update accuracy circle on mini map
  if (window.PickerMap) {
    if (pickerMarker) pickerMarker.setLatLng([ReportingState.currentLat, ReportingState.currentLon]);

    if (isRealGPS && accuracy) {
      if (pickerAccuracyCircle) window.PickerMap.removeLayer(pickerAccuracyCircle);
      pickerAccuracyCircle = L.circle([lat, lon], {
        radius: accuracy,
        color: '#2563eb',
        weight: 1.5,
        fillColor: '#3b82f6',
        fillOpacity: 0.15
      }).addTo(window.PickerMap);
    } else if (pickerAccuracyCircle) {
      window.PickerMap.removeLayer(pickerAccuracyCircle);
      pickerAccuracyCircle = null;
    }
  }

  if (!isInsideBengaluru(ReportingState.currentLat, ReportingState.currentLon)) {
    showToast('That spot is outside Bengaluru. Reports can only be submitted within Bengaluru.', 'warning');
  }

  // Trigger Reverse Geocoding to get authentic address
  performReverseGeocode(ReportingState.currentLat, ReportingState.currentLon);

  // Check duplicate near this spot
  checkDuplicateNearby(ReportingState.currentLat, ReportingState.currentLon);

  // Location priority: nearby schools / hospitals / lakes
  schedulePriorityPreview();
}

// Perform Real-World Reverse Geocoding
let geocodeRequestId = 0;
async function performReverseGeocode(lat, lon) {
  const myRequest = ++geocodeRequestId;   // a newer pin move makes this request's result stale
  const addressInput = document.getElementById('report-address');
  const wardSelect = document.getElementById('report-ward');
  const geocodeSpinner = document.getElementById('geocode-indicator');

  if (geocodeSpinner) geocodeSpinner.classList.remove('hidden');

  let resolvedAddress = '';
  let resolvedWard = '';

  // 1. Try Nominatim OpenStreetMap Reverse Geocoding API
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const nominatimUrl = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`;
    const res = await fetch(nominatimUrl, {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' }
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const geoData = await res.json();
      if (geoData && geoData.address) {
        const a = geoData.address;
        const road = a.road || a.pedestrian || a.suburb || a.neighbourhood || '';
        const suburb = a.suburb || a.city_district || a.neighbourhood || '';
        const city = a.city || a.town || 'Bengaluru';
        const postcode = a.postcode ? ` - ${a.postcode}` : '';

        if (road || suburb) {
          resolvedAddress = [road, suburb, city].filter(Boolean).join(', ') + postcode;
        }
      }
    }
  } catch (err) {
    // Nominatim timeout or blocked, fallback to internal engine
  }

  // 2. Query Local GeoAI Reverse Geocode API for precise ward & landmark detection
  try {
    const localRes = await fetch(`/api/reverse-geocode?lat=${lat}&lon=${lon}`);
    const localData = await localRes.json();
    if (localData.success) {
      if (!resolvedAddress) {
        resolvedAddress = localData.address;
      }
      resolvedWard = localData.ward_name;
    }
  } catch (err) {
    console.error('Local reverse geocode error:', err);
  }

  if (myRequest !== geocodeRequestId) return;   // user moved the pin again meanwhile: drop this result
  if (geocodeSpinner) geocodeSpinner.classList.add('hidden');

  // Overwrite the address unless the person typed their own (old check looked for the words "Bengaluru"/"Road")
  if (resolvedAddress && addressInput && !addressInput.dataset.userEdited) {
    addressInput.value = resolvedAddress;
  }

  if (resolvedWard && wardSelect) {
    // Auto-match ward in dropdown
    for (let opt of wardSelect.options) {
      if (opt.value === resolvedWard || opt.text.includes(resolvedWard)) {
        wardSelect.value = opt.value;
        break;
      }
    }
  }
}

// Duplicate Detection Check
async function checkDuplicateNearby(lat, lon) {
  try {
    const res = await fetch('/api/check-duplicate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latitude: lat, longitude: lon, threshold_m: 45.0 })
    });
    const data = await res.json();
    const alertBox = document.getElementById('duplicate-inline-alert');

    if (data.is_duplicate) {
      ReportingState.pendingDuplicateInfo = data.matched_report;
      if (alertBox) {
        alertBox.classList.remove('hidden');
        alertBox.innerHTML = `
          <div class="p-3.5 bg-amber-50/90 border border-amber-300 rounded-2xl flex items-start space-x-3 text-amber-900 text-xs shadow-sm">
            <span class="font-bold text-amber-600 text-sm">Notice:</span>
            <div class="flex-1">
              <p class="font-bold text-sm">Nearby Dump Already Reported (${data.distance_m}m away)</p>
              <p class="text-amber-800 mt-0.5">"${esc(data.matched_report.title)}" was logged by a neighbor with ${data.matched_report.upvotes || 0} upvotes.</p>
              <div class="mt-2.5 flex space-x-2">
                <button type="button" onclick="handleUpvote('${esc(data.matched_report.id)}')" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold shadow-sm transition-colors">
                  Upvote Existing Instead (+Karma)
                </button>
                <button type="button" onclick="dismissDuplicateAlert()" class="px-2.5 py-1.5 bg-white border border-amber-300 text-amber-800 rounded-xl font-semibold hover:bg-amber-100 transition-colors">
                  Submit New Spot
                </button>
              </div>
            </div>
          </div>
        `;
      }
    } else {
      ReportingState.pendingDuplicateInfo = null;
      if (alertBox) alertBox.classList.add('hidden');
    }
  } catch (err) {
    console.error('Duplicate check failed:', err);
  }
}

function dismissDuplicateAlert() {
  const alertBox = document.getElementById('duplicate-inline-alert');
  if (alertBox) alertBox.classList.add('hidden');
}

// Photo Upload & AI Vision Setup
function setupPhotoUpload() {
  const fileInput = document.getElementById('photo-upload-input');
  const previewImg = document.getElementById('photo-preview-img');
  const placeholderBox = document.getElementById('photo-placeholder-box');
  const dropzone = document.getElementById('upload-dropzone-box');

  if (!fileInput) return;

  const handleFile = async (file) => {
    if (!file || !file.type.startsWith('image/')) {
      showToast('Please select a valid image file', 'warning');
      return;
    }

    ReportingState.selectedFile = file;

    const reader = new FileReader();
    reader.onload = (re) => {
      if (previewImg) {
        previewImg.src = re.target.result;
        previewImg.classList.remove('hidden');
      }
      if (placeholderBox) placeholderBox.classList.add('hidden');
    };
    reader.readAsDataURL(file);

  };

  fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFile(e.target.files[0]);
  });

  // Drag & drop support
  if (dropzone) {
    ['dragenter', 'dragover'].forEach(event => {
      dropzone.addEventListener(event, (e) => {
        e.preventDefault();
        dropzone.classList.add('border-emerald-500', 'bg-emerald-50/50');
      });
    });
    ['dragleave', 'drop'].forEach(event => {
      dropzone.addEventListener(event, (e) => {
        e.preventDefault();
        dropzone.classList.remove('border-emerald-500', 'bg-emerald-50/50');
      });
    });
    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    });
  }
}

// Run AI Waste Classification
async function runAIClassification(file) {
  const aiResultsBox = document.getElementById('ai-results-panel');
  if (aiResultsBox) {
    aiResultsBox.classList.remove('hidden');
    aiResultsBox.innerHTML = `
      <div class="p-5 bg-emerald-50/70 border border-emerald-200 rounded-2xl flex items-center space-x-3 text-emerald-800">
        <svg class="animate-spin h-5 w-5 text-emerald-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <span class="text-xs font-bold tracking-wide">GeoAI WasteNet analyzing material textures, volume &amp; hazard level...</span>
      </div>
    `;
  }

  try {
    const formData = new FormData();
    formData.append('photo', file);
    formData.append('description', document.getElementById('report-desc')?.value || '');

    const res = await fetch('/api/ai-classify', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success && data.analysis) {
      const a = data.analysis;
      ReportingState.aiResult = a;

      const catSelect = document.getElementById('report-category');
      const sevSelect = document.getElementById('report-severity');
      const titleInput = document.getElementById('report-title');

      if (catSelect) catSelect.value = a.category;
      if (sevSelect) sevSelect.value = a.severity;
      if (titleInput && (!titleInput.value || titleInput.value.includes('Illegal Dump') || titleInput.value.includes('Roadside'))) {
        titleInput.value = `${a.category} Dumping Pile`;
      }

      renderAIAnalysisCard(a);
      showToast(`${a.is_demo_heuristic ? 'Keyword guess (not image analysis)' : 'AI classified'}: ${a.category} (${a.confidence_percentage}% confidence)`, 'success');
    }
  } catch (err) {
    console.error('AI Classification failed:', err);
    if (aiResultsBox) {
      aiResultsBox.innerHTML = `<p class="text-xs text-rose-600 p-2">AI analysis service unavailable. Category can be selected manually.</p>`;
    }
  }
}

function renderAIAnalysisCard(analysis) {
  const aiResultsBox = document.getElementById('ai-results-panel');
  if (!aiResultsBox) return;

  const materialsHtml = (analysis.detected_materials || []).map(m => `
    <span class="bg-white/90 text-emerald-800 border border-emerald-200 px-2.5 py-1 rounded-lg text-xs font-semibold shadow-xs">${esc(m)}</span>
  `).join(' ');

  const risksHtml = (analysis.environmental_risks || []).map(r => `
    <li class="flex items-center space-x-1.5"><span class="text-rose-500 font-bold">•</span><span>${esc(r)}</span></li>
  `).join('');

  aiResultsBox.innerHTML = `
    <div class="p-5 bg-gradient-to-br from-emerald-50 via-teal-50/50 to-white border border-emerald-200 rounded-3xl shadow-sm text-slate-800">
      <div class="flex items-center justify-between mb-2.5">
        <span class="text-xs font-extrabold text-emerald-800 tracking-wider uppercase flex items-center">
          <span>${analysis.is_demo_heuristic ? 'Keyword guess (demo, photo not analysed)' : 'AI Vision (' + esc(analysis.ai_model) + ')'}</span>
        </span>
        <span class="bg-emerald-600 text-white text-xs font-extrabold px-3 py-0.5 rounded-full shadow-sm">
          ${esc(analysis.confidence_percentage)}% Confidence
        </span>
      </div>

      <div class="mb-3.5">
        <h4 class="font-extrabold text-lg text-slate-900 leading-snug">${esc(analysis.category)}</h4>
        <span class="inline-block text-xs text-emerald-700 font-semibold bg-emerald-100/70 px-2 py-0.5 rounded-md mt-1">
          Recyclability: ${esc(analysis.recyclability)}
        </span>
      </div>

      <div class="grid grid-cols-2 gap-2.5 mb-3.5 text-xs">
        <div class="bg-white/90 p-2.5 rounded-xl border border-emerald-100 shadow-xs">
          <span class="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">Est. Volume:</span>
          <span class="font-extrabold text-slate-800 text-sm">${esc(analysis.estimated_volume_m3)}</span>
          <span class="text-[11px] text-slate-500 block">(~${esc(analysis.estimated_weight_kg)} kg${analysis.is_demo_heuristic ? ", category average" : ""})</span>
        </div>
        <div class="bg-white/90 p-2.5 rounded-xl border border-emerald-100 shadow-xs">
          <span class="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">Recommended Truck:</span>
          <span class="font-extrabold text-slate-800 text-xs block truncate mt-0.5">${esc(analysis.truck_dispatch_type)}</span>
          <span class="text-[11px] text-emerald-600 block">Auto-Routing Enabled</span>
        </div>
      </div>

      <div class="mb-3">
        <span class="text-xs font-bold text-slate-700 block mb-1.5">Identified Materials:</span>
        <div class="flex flex-wrap gap-1.5">${materialsHtml}</div>
      </div>

      <div class="pt-3 border-t border-emerald-200/60 text-xs">
        <span class="font-bold text-rose-700 block mb-1">Public &amp; Ecological Hazards:</span>
        <ul class="text-slate-600 space-y-0.5 text-[11px]">${risksHtml}</ul>
      </div>
    </div>
  `;
}

// Form Submission
function setupReportForm() {
  const form = document.getElementById('report-waste-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const title = document.getElementById('report-title')?.value || 'Illegal Waste Dump';
    const description = document.getElementById('report-desc')?.value || '';
    const category = document.getElementById('report-category')?.value;
    const severity = document.getElementById('report-severity')?.value;
    const wardName = '';  // ward is derived server-side from the coordinates
    const address = document.getElementById('report-address')?.value || '';

    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    formData.append('category', category);
    formData.append('severity', severity);
    formData.append('ward_name', wardName);
    formData.append('address', address);
    formData.append('latitude', ReportingState.currentLat);
    formData.append('longitude', ReportingState.currentLon);

    if (ReportingState.selectedFile) {
      formData.append('photo', ReportingState.selectedFile);
    }

    const submitBtn = document.getElementById('btn-submit-report');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <svg class="animate-spin h-4 w-4 mr-2 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg> Submitting Report...
      `;
    }

    try {
      const res = await fetch('/api/reports', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (res.status === 409 && data.is_duplicate) {
        showToast('Duplicate dump found nearby! You can upvote the existing one.', 'warning');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Submit Citizen Report';
        }
        return;
      }

      if (data.success) {
        showToast('Report logged successfully!', 'success');
        form.reset();
        const addrEl = document.getElementById('report-address');
        if (addrEl) delete addrEl.dataset.userEdited;
        ReportingState.selectedFile = null;
        ReportingState.aiResult = null;
        const preview = document.getElementById('photo-preview-img');
        const placeholder = document.getElementById('photo-placeholder-box');
        const aiBox = document.getElementById('ai-results-panel');
        if (preview) preview.classList.add('hidden');
        if (placeholder) placeholder.classList.remove('hidden');
        if (aiBox) aiBox.classList.add('hidden');

        const newReport = data.report;
        await fetchReports();
        // On serverless hosting a different server instance may answer the list request,
        // so make sure the report we just created is always shown.
        if (newReport && !AppState.reports.some(r => r.id === newReport.id)) {
          AppState.reports.push(newReport);
          updateHeaderKPIs();
        }
        switchTab('map-view');
        if (typeof renderMarkers === 'function') renderMarkers(AppState.reports);
        if (newReport && typeof focusReportOnMap === 'function') focusReportOnMap(newReport);
      } else {
        showToast(data.error || 'Failed to submit report', 'error');
      }
    } catch (err) {
      console.error('Submission failed:', err);
      showToast('Saved to offline sync queue.', 'info');
      AppState.offlineQueue.push({
        title, description, category, severity, ward_name: wardName, address,
        latitude: ReportingState.currentLat, longitude: ReportingState.currentLon,
        timestamp: new Date().toISOString()
      });
      localStorage.setItem('gwr_offline_queue', JSON.stringify(AppState.offlineQueue));
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Submit Citizen Report';
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupPhotoUpload();
  setupReportForm();

  const addressField = document.getElementById('report-address');
  if (addressField) addressField.addEventListener('input', () => { addressField.dataset.userEdited = '1'; });

  const sevSelect = document.getElementById('report-severity');
  if (sevSelect) sevSelect.addEventListener('change', schedulePriorityPreview);
  schedulePriorityPreview();

  const gpsBtn = document.getElementById('btn-get-gps');
  if (gpsBtn) gpsBtn.addEventListener('click', triggerRealGPS);

  // Setup Preset Buttons
  document.querySelectorAll('.btn-gps-preset').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const presetKey = e.currentTarget.dataset.preset;
      applyGPSPreset(presetKey);
    });
  });
});


// ---------------------------------------------------------------------------------------------
// Location priority preview: draws nearby schools / hospitals / lakes + distance rings on the map
// ---------------------------------------------------------------------------------------------
let priorityLayer = null;
let priorityTimer = null;
let priorityRequestId = 0;

const RECEPTOR_STYLE = {
  school:     { color: '#2563eb', label: 'School' },
  hospital:   { color: '#dc2626', label: 'Hospital / clinic' },
  water_body: { color: '#0891b2', label: 'Water body' }
};
const LEVEL_CLASS = {
  Critical: 'bg-red-100 text-red-700 border-red-200',
  High:     'bg-orange-100 text-orange-700 border-orange-200',
  Medium:   'bg-yellow-100 text-yellow-700 border-yellow-200',
  Low:      'bg-green-100 text-green-700 border-green-200'
};

function schedulePriorityPreview() {
  clearTimeout(priorityTimer);
  priorityTimer = setTimeout(refreshPriorityPreview, 400);
}

async function refreshPriorityPreview() {
  const box = document.getElementById('priority-preview');
  if (!box) return;
  const myRequest = ++priorityRequestId;
  const lat = ReportingState.currentLat, lon = ReportingState.currentLon;
  const sev = document.getElementById('report-severity')?.value || 3;

  box.innerHTML = '<p class="text-xs text-slate-500 px-1">Checking for nearby schools, hospitals and lakes...</p>';
  try {
    const res = await fetch(`/api/priority-preview?lat=${lat}&lon=${lon}&severity=${sev}`);
    const d = await res.json();
    if (myRequest !== priorityRequestId) return;   // a newer pin move superseded this one
    if (!d.success) throw new Error(d.error || 'failed');
    drawPriorityOnMap(d, lat, lon);
    renderPriorityBox(box, d);
  } catch (err) {
    if (myRequest !== priorityRequestId) return;
    box.innerHTML = '<p class="text-xs text-rose-600 px-1">Could not calculate location priority. Try moving the pin again.</p>';
  }
}

function drawPriorityOnMap(d, lat, lon) {
  const map = window.PickerMap;
  if (!map) return;
  if (priorityLayer) map.removeLayer(priorityLayer);
  priorityLayer = L.layerGroup().addTo(map);

  // Distance rings used by the scoring rule
  [[700, '#eab308'], [350, '#f97316'], [150, '#ef4444']].forEach(([radius, color]) => {
    L.circle([lat, lon], { radius, color, weight: 1.5, dashArray: '5 5', fillColor: color,
                           fillOpacity: 0.05, interactive: false }).addTo(priorityLayer);
  });

  (d.receptors || []).forEach(r => {
    const st = RECEPTOR_STYLE[r.type] || { color: '#64748b', label: 'Place' };
    const isBest = d.closest_receptor && r.name === d.closest_receptor.name && r.type === d.closest_receptor.type;
    const m = L.circleMarker([r.lat, r.lon], {
      radius: isBest ? 10 : 7, color: '#ffffff', weight: 2, fillColor: st.color, fillOpacity: 0.95
    }).addTo(priorityLayer);
    m.bindTooltip(`${esc(r.name)} · ${Math.round(r.distance_m)} m`, { permanent: isBest, direction: 'top', offset: [0, -6] });
  });

  // Make sure the rings and places are visible
  if (map.getZoom() < 15) map.setView([lat, lon], 16);
}

function renderPriorityBox(box, d) {
  const cls = LEVEL_CLASS[d.level] || LEVEL_CLASS.Medium;
  const rows = (d.receptors || []).slice(0, 5).map(r => {
    const st = RECEPTOR_STYLE[r.type] || { color: '#64748b', label: 'Place' };
    return `<li class="flex items-center justify-between text-[11px] text-slate-700">
      <span class="flex items-center space-x-1.5"><span class="inline-block w-2.5 h-2.5 rounded-full" style="background:${st.color}"></span><span>${esc(r.name)}</span></span>
      <span class="font-bold">${Math.round(r.distance_m)} m</span></li>`;
  }).join('');
  const sourceNote = d.source === 'openstreetmap' ? '' :
    '<p class="text-[10px] text-amber-700 mt-2">Live OpenStreetMap lookup unavailable right now, so only a short built-in list of places was checked.</p>';
  box.innerHTML = `
    <div class="border border-slate-200 rounded-2xl p-3 bg-white shadow-xs">
      <div class="flex items-center justify-between">
        <span class="text-[11px] font-extrabold uppercase tracking-wider text-slate-500">Location priority</span>
        <span class="text-xs font-extrabold px-2.5 py-1 rounded-full border ${cls}">${esc(d.level)} · ${d.score}/100</span>
      </div>
      <p class="text-xs font-semibold text-slate-800 mt-1.5">${esc(d.proximity_note)}</p>
      ${d.escalated ? '<p class="text-[11px] font-bold text-red-600 mt-1">Urgent: very close to a school or hospital.</p>' : ''}
      ${rows ? `<ul class="mt-2 space-y-1 border-t border-slate-100 pt-2">${rows}</ul>` : ''}
      <p class="text-[10px] text-slate-400 mt-2">Rings on the map: 150 m / 350 m / 700 m from the pin.</p>
      ${sourceNote}
    </div>`;
}
