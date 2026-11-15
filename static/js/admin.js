/**
 * Municipal Admin Management & Before/After Proof Controller
 */

window.AdminManager = {
  activeReportId: null,

  render: function() {
    this.renderTable(AppState.reports);
  },

  renderTable: function(reports) {
    const tbody = document.getElementById('admin-reports-tbody');
    if (!tbody) return;

    if (!reports || reports.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400">No reports match the current filters.</td></tr>`;
      return;
    }

    tbody.innerHTML = reports.map(r => {
      const statusBadges = {
        'Reported': 'bg-rose-50 text-rose-700 border border-rose-200',
        'In Progress': 'bg-amber-50 text-amber-700 border border-amber-200',
        'Cleared': 'bg-emerald-50 text-emerald-700 border border-emerald-200'
      };

      const priorityBadges = {
        'Critical': 'bg-rose-600 text-white shadow-xs',
        'High': 'bg-orange-500 text-white shadow-xs',
        'Medium': 'bg-amber-500 text-white shadow-xs',
        'Low': 'bg-emerald-600 text-white shadow-xs'
      };

      const timeAgo = formatRelativeTime(r.reported_at);

      // Distance from user GPS
      let distBadge = '';
      if (window.MapLayers && MapLayers.userLocation) {
        const d = calculateHaversine(
          MapLayers.userLocation.lat,
          MapLayers.userLocation.lon,
          r.latitude,
          r.longitude
        );
        const dStr = d < 1000 ? `${Math.round(d)}m` : `${(d / 1000).toFixed(1)}km`;
        distBadge = `<span class="text-[10px] text-blue-600 font-bold bg-blue-50 px-1.5 py-0.5 rounded ml-1">${dStr} away</span>`;
      }

      return `
        <tr class="border-b border-slate-100 hover:bg-slate-50/80 transition-colors">
          <td class="py-3 px-4">
            <div class="flex items-center space-x-3">
              <img src="${esc(r.image_url)}" alt="photo" class="w-12 h-12 rounded-xl object-cover border border-slate-200 shadow-xs shrink-0" />
              <div>
                <div class="flex items-center space-x-1.5">
                  <span class="text-[10px] font-mono font-extrabold text-slate-400">${esc(r.id)}</span>
                  ${distBadge}
                </div>
                <h5 class="text-xs font-bold text-slate-900 leading-snug">${esc(r.title)}</h5>
                <span class="text-[11px] text-slate-500">${esc(r.ward_name)}</span>
              </div>
            </div>
          </td>
          <td class="py-3 px-4">
            <span class="text-[11px] font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-lg">${esc(r.category)}</span>
          </td>
          <td class="py-3 px-4">
            <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-full ${priorityBadges[r.priority_level] || 'bg-slate-500 text-white'}">
              ${r.priority_level} (${Math.round(r.priority_score)})
            </span>
          </td>
          <td class="py-3 px-4">
            <span class="text-[10px] font-bold px-2.5 py-1 rounded-full ${statusBadges[r.status] || 'bg-slate-100'}">
              ${r.status}
            </span>
          </td>
          <td class="py-3 px-4 text-xs font-bold text-slate-600">
            <span>${r.upvotes || 0} votes</span>
          </td>
          <td class="py-3 px-4 text-[11px] text-slate-500">
            ${timeAgo}
          </td>
          <td class="py-3 px-4 text-right">
            <button onclick="openAdminModal('${esc(r.id)}')" class="px-3.5 py-1.5 bg-slate-900 hover:bg-emerald-600 text-white text-xs font-bold rounded-xl shadow-xs transition-all hover:scale-105 active:scale-95">
              Inspect &amp; Proof →
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }
};

// Open Admin Modal for single report
async function openAdminModal(reportId) {
  AdminManager.activeReportId = reportId;
  const modal = document.getElementById('admin-action-modal');
  if (!modal) return;

  try {
    const res = await fetch(`/api/reports/${reportId}`);
    const data = await res.json();
    if (!data.success) {
      showToast('Could not fetch report details', 'error');
      return;
    }

    const r = data.report;
    document.getElementById('modal-report-id').innerText = r.id;
    document.getElementById('modal-report-title').innerText = r.title;
    document.getElementById('modal-report-category').innerText = r.category;
    document.getElementById('modal-report-ward').innerText = r.ward_name;
    document.getElementById('modal-report-score').innerText = `${Math.round(r.priority_score)}/100 (${r.priority_level})`;
    document.getElementById('modal-report-status-select').value = r.status;
    document.getElementById('modal-supervisor-notes').value = r.notes || '';

    // Before / After View
    const beforeImg = document.getElementById('modal-before-img');
    const afterImg = document.getElementById('modal-after-img');
    const baContainer = document.getElementById('modal-ba-slider');

    if (beforeImg) beforeImg.src = r.image_url;

    if (r.after_image_url) {
      if (afterImg) afterImg.src = r.after_image_url;
      if (baContainer) baContainer.classList.remove('hidden');
    } else {
      if (baContainer) baContainer.classList.add('hidden');
    }

    // Render Audit Trail
    const auditBox = document.getElementById('modal-audit-trail');
    if (auditBox && r.audit_trail) {
      auditBox.innerHTML = r.audit_trail.map(a => `
        <li class="border-l-2 border-emerald-500 pl-3 py-1 text-xs">
          <span class="font-bold text-slate-800">${esc(a.actor)}</span>
          <span class="text-slate-400 text-[10px] ml-1">(${formatRelativeTime(a.timestamp)})</span>
          <p class="text-slate-600">${esc(a.details)}</p>
        </li>
      `).join('');
    }

    modal.classList.remove('hidden');
  } catch (err) {
    console.error('Error opening admin modal:', err);
  }
}

function closeAdminModal() {
  const modal = document.getElementById('admin-action-modal');
  if (modal) modal.classList.add('hidden');
  AdminManager.activeReportId = null;
}

// Save Admin Updates (Status & Proof)
async function submitAdminUpdate() {
  const reportId = AdminManager.activeReportId;
  if (!reportId) return;

  const newStatus = document.getElementById('modal-report-status-select')?.value;
  const notes = document.getElementById('modal-supervisor-notes')?.value;
  const afterFileInput = document.getElementById('modal-after-photo-input');

  const formData = new FormData();
  formData.append('status', newStatus);
  formData.append('notes', notes);
  formData.append('actor', 'Municipal Supervisor (BBMP)');

  if (afterFileInput && afterFileInput.files[0]) {
    formData.append('after_photo', afterFileInput.files[0]);
  }

  try {
    const res = await adminFetch(`/api/reports/${reportId}/status`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Report ${reportId} marked as ${newStatus}!`, 'success');
      closeAdminModal();
      await fetchReports();
      if (window.MainMap) window.MainMap.refreshHotspots();
    } else {
      showToast(data.error || 'Failed to update status', 'error');
    }
  } catch (err) {
    showToast('Failed to connect to server', 'error');
  }
}

// Setup Before / After Slider Interaction
function setupBeforeAfterSlider() {
  const container = document.getElementById('modal-ba-slider');
  const overlay = document.getElementById('ba-overlay-box');
  const handle = document.getElementById('ba-handle-btn');

  if (!container || !overlay || !handle) return;

  let isDragging = false;

  const updatePosition = (clientX) => {
    const rect = container.getBoundingClientRect();
    let x = clientX - rect.left;
    x = Math.max(0, Math.min(x, rect.width));
    const percent = (x / rect.width) * 100;
    overlay.style.width = `${percent}%`;
    handle.style.left = `${percent}%`;
  };

  handle.addEventListener('mousedown', () => isDragging = true);
  window.addEventListener('mouseup', () => isDragging = false);
  window.addEventListener('mousemove', (e) => {
    if (isDragging) updatePosition(e.clientX);
  });

  // Touch Support
  handle.addEventListener('touchstart', () => isDragging = true);
  window.addEventListener('touchend', () => isDragging = false);
  window.addEventListener('touchmove', (e) => {
    if (isDragging && e.touches[0]) updatePosition(e.touches[0].clientX);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupBeforeAfterSlider();
  const saveBtn = document.getElementById('btn-save-admin-modal');
  if (saveBtn) saveBtn.addEventListener('click', submitAdminUpdate);
  const cancelBtn = document.getElementById('btn-cancel-admin-modal');
  if (cancelBtn) cancelBtn.addEventListener('click', closeAdminModal);
});
