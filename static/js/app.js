/**
 * Main Application Controller for Geo-Waste Reporter
 */

const AppState = {
  currentTab: 'map-view',
  reports: [],
  selectedReport: null,
  filters: {
    status: 'All',
    category: 'All',
    ward: 'All',
    priority: 'All',
    search: ''
  },
  offlineQueue: JSON.parse(localStorage.getItem('gwr_offline_queue') || '[]'),
  isOnline: navigator.onLine
};

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const bgColors = {
    success: 'bg-emerald-600',
    error: 'bg-rose-600',
    warning: 'bg-amber-500',
    info: 'bg-slate-800'
  };

  const icons = {
    success: '✓',
    error: '✕',
    warning: '!',
    info: 'i'
  };

  const toast = document.createElement('div');
  toast.className = `${bgColors[type] || bgColors.info} text-white px-4 py-3 rounded-xl shadow-lg flex items-center space-x-3 text-sm font-medium transform transition-all duration-300 translate-y-2 opacity-0`;
  toast.innerHTML = `
    <span class="font-bold text-base">${icons[type] || '•'}</span>
    <span class="flex-1">${message}</span>
  `;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function switchTab(tabId) {
  AppState.currentTab = tabId;

  // Update nav buttons
  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    if (btn.dataset.tab === tabId) {
      btn.className = 'nav-tab-btn flex items-center space-x-2 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-white text-emerald-700 shadow-xs border border-slate-200/60 transition-all';
    } else {
      btn.className = 'nav-tab-btn flex items-center space-x-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 transition-all';
    }
  });

  // Toggle tab sections
  document.querySelectorAll('.tab-section').forEach(sec => {
    sec.classList.add('hidden');
  });

  const activeSection = document.getElementById(tabId);
  if (activeSection) {
    activeSection.classList.remove('hidden');
  }

  // Trigger resize or load events for specific views
  if (tabId === 'map-view' && window.MainMap) {
    setTimeout(() => window.MainMap.invalidateSize(), 150);
  } else if (tabId === 'report-view') {
    if (typeof initPickerMap === 'function' && !window.PickerMap) {
      initPickerMap();
    }
    setTimeout(() => {
      if (window.PickerMap) window.PickerMap.invalidateSize();
    }, 150);
  } else if (tabId === 'analytics-view' && window.AnalyticsManager) {
    window.AnalyticsManager.render();
  } else if (tabId === 'admin-view' && window.AdminManager) {
    window.AdminManager.render();
  } else if (tabId === 'route-view' && window.RouteOptimizer) {
    setTimeout(() => {
      if (window.RouteMap) window.RouteMap.invalidateSize();
      window.RouteOptimizer.loadRoute();
    }, 200);
  }
}

// Fetch all reports from API
async function fetchReports() {
  try {
    const params = new URLSearchParams();
    if (AppState.filters.status !== 'All') params.append('status', AppState.filters.status);
    if (AppState.filters.category !== 'All') params.append('category', AppState.filters.category);
    if (AppState.filters.ward !== 'All') params.append('ward', AppState.filters.ward);
    if (AppState.filters.priority !== 'All') params.append('priority', AppState.filters.priority);
    if (AppState.filters.search) params.append('search', AppState.filters.search);

    const res = await fetch(`/api/reports?${params.toString()}`);
    const data = await res.json();
    if (data.success) {
      AppState.reports = data.reports;
      updateHeaderKPIs();
      if (window.MainMap) window.MainMap.renderMarkers(AppState.reports);
      if (window.AdminManager) window.AdminManager.renderTable(AppState.reports);
      return data.reports;
    }
  } catch (err) {
    console.error('Failed to fetch reports:', err);
    showToast('Failed to load reports from server', 'error');
  }
  return [];
}

// Update Top KPI counters
function updateHeaderKPIs() {
  const total = AppState.reports.length;
  const reported = AppState.reports.filter(r => r.status === 'Reported').length;
  const inProgress = AppState.reports.filter(r => r.status === 'In Progress').length;
  const cleared = AppState.reports.filter(r => r.status === 'Cleared').length;
  const critical = AppState.reports.filter(r => r.priority_level === 'Critical' && r.status !== 'Cleared').length;

  const kpiTotal = document.getElementById('kpi-total');
  const kpiReported = document.getElementById('kpi-reported');
  const kpiProgress = document.getElementById('kpi-progress');
  const kpiCleared = document.getElementById('kpi-cleared');
  const kpiCritical = document.getElementById('kpi-critical');

  if (kpiTotal) kpiTotal.innerText = total;
  if (kpiReported) kpiReported.innerText = reported;
  if (kpiProgress) kpiProgress.innerText = inProgress;
  if (kpiCleared) kpiCleared.innerText = cleared;
  if (kpiCritical) kpiCritical.innerText = critical;
}

// Reseed Database Trigger
async function triggerReseed() {
  if (!confirm('Reset and reseed database with 55 realistic Bengaluru dumping reports?')) return;
  try {
    const res = await fetch('/api/seed', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('Database successfully reseeded!', 'success');
      await fetchReports();
      if (window.MainMap) window.MainMap.refreshHotspots();
      if (window.AnalyticsManager) window.AnalyticsManager.render();
    }
  } catch (err) {
    showToast('Failed to reseed database', 'error');
  }
}

// Setup Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  // Navigation tabs
  document.querySelectorAll('.nav-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Filter Bar controls
  const statusFilter = document.getElementById('filter-status');
  const categoryFilter = document.getElementById('filter-category');
  const wardFilter = document.getElementById('filter-ward');
  const priorityFilter = document.getElementById('filter-priority');
  const searchInput = document.getElementById('filter-search');

  const onFilterChange = () => {
    if (statusFilter) AppState.filters.status = statusFilter.value;
    if (categoryFilter) AppState.filters.category = categoryFilter.value;
    if (wardFilter) AppState.filters.ward = wardFilter.value;
    if (priorityFilter) AppState.filters.priority = priorityFilter.value;
    if (searchInput) AppState.filters.search = searchInput.value.trim();
    fetchReports();
  };

  if (statusFilter) statusFilter.addEventListener('change', onFilterChange);
  if (categoryFilter) categoryFilter.addEventListener('change', onFilterChange);
  if (wardFilter) wardFilter.addEventListener('change', onFilterChange);
  if (priorityFilter) priorityFilter.addEventListener('change', onFilterChange);
  if (searchInput) searchInput.addEventListener('input', debounce(onFilterChange, 350));

  // Reseed button
  const reseedBtn = document.getElementById('btn-reseed');
  if (reseedBtn) reseedBtn.addEventListener('click', triggerReseed);

  // Initial fetch
  fetchReports();
});

// Utility Debounce
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Format relative date
function formatRelativeTime(dateStr) {
  if (!dateStr) return 'Unknown';
  const d = new Date(dateStr);
  const now = new Date();
  const diffSec = Math.floor((now - d) / 1000);

  if (diffSec < 60) return 'Just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} mins ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hrs ago`;
  const days = Math.floor(diffSec / 86400);
  return `${days} ${days === 1 ? 'day' : 'days'} ago`;
}
