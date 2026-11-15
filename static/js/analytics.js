/**
 * Analytics & Trends Dashboard Controller
 * Chart.js Visualizations & Ward Cleanliness Leaderboard
 */

window.AnalyticsManager = {
  timelineChart: null,
  categoryChart: null,
  priorityChart: null,

  render: async function() {
    await this.loadSummary();
    await this.loadWardLeaderboard();
  },

  loadSummary: async function() {
    try {
      const res = await fetch('/api/analytics');
      const data = await res.json();
      if (!data.success) return;

      // Update KPI Cards
      const totalElem = document.getElementById('analytics-total');
      const rateElem = document.getElementById('analytics-rate');
      const avgTimeElem = document.getElementById('analytics-avg-time');

      if (totalElem) totalElem.innerText = data.total_reports;
      if (rateElem) rateElem.innerText = `${data.clearance_rate_percent}%`;
      if (avgTimeElem) avgTimeElem.innerText = `${data.average_resolution_hours} hrs`;

      // 1. Timeline Line Chart
      this.renderTimelineChart(data.timeline || []);

      // 2. Category Doughnut Chart
      this.renderCategoryChart(data.category_counts || {});

      // 3. Priority Bar Chart
      this.renderPriorityChart(data.priority_counts || {});
    } catch (err) {
      console.error('Failed to load analytics summary:', err);
    }
  },

  renderTimelineChart: function(timeline) {
    const ctx = document.getElementById('chart-timeline');
    if (!ctx) return;

    const labels = timeline.map(t => t.date.slice(5)); // MM-DD
    const counts = timeline.map(t => t.count);

    if (this.timelineChart) this.timelineChart.destroy();

    this.timelineChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Dump Reports Logged',
          data: counts,
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#059669',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  renderCategoryChart: function(catCounts) {
    const ctx = document.getElementById('chart-category');
    if (!ctx) return;

    const labels = Object.keys(catCounts);
    const data = Object.values(catCounts);

    const colors = [
      '#0284c7', // Plastic (Blue)
      '#ea580c', // C&D Debris (Orange)
      '#16a34a', // Organic (Green)
      '#475569', // E-waste (Slate)
      '#dc2626', // Hazardous (Red)
      '#d97706'  // Mixed (Amber)
    ];

    if (this.categoryChart) this.categoryChart.destroy();

    this.categoryChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors.slice(0, labels.length),
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
        },
        cutout: '65%'
      }
    });
  },

  renderPriorityChart: function(priorityCounts) {
    const ctx = document.getElementById('chart-priority');
    if (!ctx) return;

    const levels = ['Critical', 'High', 'Medium', 'Low'];
    const data = levels.map(l => priorityCounts[l] || 0);
    const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e'];

    if (this.priorityChart) this.priorityChart.destroy();

    this.priorityChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: levels,
        datasets: [{
          data: data,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  loadWardLeaderboard: async function() {
    try {
      const res = await fetch('/api/wards');
      const data = await res.json();
      if (!data.success) return;

      const container = document.getElementById('ward-leaderboard-tbody');
      if (!container) return;

      container.innerHTML = data.ward_leaderboard.map((w, idx) => {
        let badgeColor = 'bg-emerald-100 text-emerald-800';
        if (w.grade.startsWith('C')) badgeColor = 'bg-amber-100 text-amber-800';
        if (w.grade.startsWith('D')) badgeColor = 'bg-rose-100 text-rose-800';

        return `
          <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
            <td class="py-2.5 px-3 font-bold text-slate-500 text-xs">#${idx + 1}</td>
            <td class="py-2.5 px-3">
              <span class="font-bold text-slate-900 text-sm block">${esc(w.ward_name)}</span>
              <span class="text-xs text-slate-400">${w.ward_id}</span>
            </td>
            <td class="py-2.5 px-3 text-xs font-semibold text-slate-700">${w.total_reports}</td>
            <td class="py-2.5 px-3 text-xs font-bold text-rose-600">${w.open_reports}</td>
            <td class="py-2.5 px-3 text-xs font-semibold text-emerald-600">${w.cleared_reports}</td>
            <td class="py-2.5 px-3 text-xs">
              <div class="flex items-center space-x-2">
                <div class="w-16 bg-slate-200 rounded-full h-2 overflow-hidden">
                  <div class="bg-emerald-500 h-2 rounded-full" style="width: ${w.clearance_rate}%"></div>
                </div>
                <span class="font-bold text-slate-700 text-xs">${w.clearance_rate}%</span>
              </div>
            </td>
            <td class="py-2.5 px-3 text-xs font-bold text-slate-800">${w.cleanliness_index}/100</td>
            <td class="py-2.5 px-3 text-right">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full ${badgeColor}">
                ${w.grade}
              </span>
            </td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.error('Failed to load ward leaderboard:', err);
    }
  }
};
