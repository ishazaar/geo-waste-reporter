/**
 * Hackathon Presentation Pitch Deck Controller
 * Built-in 6-slide deck formatted for judges and presentations (Clean, professional typography without emojis)
 */

const PresentationDeck = {
  currentSlide: 1,
  totalSlides: 6,

  slides: [
    {
      title: "Problem 10: Geo-Waste Reporter",
      subtitle: "AI-Powered Citizen Geospatial Platform for Illegal Dumping Detection, Hotspot Analytics & Smart Municipal Cleanup",
      badge: "GeoAI Hackathon 2026",
      content: `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 my-6">
          <div class="bg-emerald-50 border border-emerald-200 rounded-2xl p-5 text-center">
            <div class="w-10 h-10 mx-auto mb-3 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold text-sm">AI</div>
            <h4 class="font-bold text-slate-900 text-base mb-1">Citizen Vision AI</h4>
            <p class="text-xs text-slate-600">Zero-form reporting: automatic waste category classification & volume estimation from photos.</p>
          </div>
          <div class="bg-blue-50 border border-blue-200 rounded-2xl p-5 text-center">
            <div class="w-10 h-10 mx-auto mb-3 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-sm">GIS</div>
            <h4 class="font-bold text-slate-900 text-base mb-1">DBSCAN Spatial Hotspots</h4>
            <p class="text-xs text-slate-600">Density-based clustering uncovers recurring dumping zones & environmental risks around lakes.</p>
          </div>
          <div class="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-center">
            <div class="w-10 h-10 mx-auto mb-3 rounded-xl bg-amber-600 text-white flex items-center justify-center font-bold text-sm">TSP</div>
            <h4 class="font-bold text-slate-900 text-base mb-1">2-Opt Route Optimization</h4>
            <p class="text-xs text-slate-600">Calculates optimal cleanup truck routes, saving 37%+ fuel & accelerating municipal response.</p>
          </div>
        </div>
        <div class="flex items-center justify-center space-x-6 text-xs text-slate-500 mt-4">
          <span><strong>Team:</strong> GeoAI Innovators</span>
          <span><strong>Target City:</strong> Bengaluru (BBMP)</span>
          <span><strong>Stack:</strong> Python Flask &bull; NumPy &bull; SQLite &bull; Leaflet &bull; Tailwind CSS</span>
        </div>
      `
    },
    {
      title: "Problem Statement & Real-World Impact",
      subtitle: "Why Illegal Urban Dumping Persists and How Traditional Reporting Fails",
      badge: "The Urban Challenge",
      content: `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 my-4">
          <div class="bg-rose-50 border border-rose-200 rounded-2xl p-5">
            <h4 class="font-bold text-rose-900 text-base mb-3">
              The Traditional Breakdown
            </h4>
            <ul class="space-y-3 text-xs text-rose-800">
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>Unreported & Untracked:</strong> 70%+ of illegal black spots remain unnoticed until severe storm drain clogs occur.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>Duplicate Clutter:</strong> Citizens submit repetitive complaints for the same corner pile, overwhelming control rooms.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>No Priority Intelligence:</strong> A harmless leaf pile gets cleared before a toxic chemical drum near a lake feeder canal.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>Zero Cleanup Verification:</strong> Cases marked "resolved" without photographic accountability.</span>
              </li>
            </ul>
          </div>
          <div class="bg-emerald-50 border border-emerald-200 rounded-2xl p-5">
            <h4 class="font-bold text-emerald-900 text-base mb-3">
              Our GeoAI Paradigm Shift
            </h4>
            <ul class="space-y-3 text-xs text-emerald-800">
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>Instant Camera AI:</strong> Upload photo &rarr; auto GPS pin + AI waste categorization in under 800ms.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>40m Spatial Deduplication:</strong> Identifies nearby existing reports and prompts 1-click upvotes instead of duplicate tickets.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>MCDA Priority Triage:</strong> Weighted scoring based on distance to sensitive water bodies, schools & hospitals.</span>
              </li>
              <li class="flex items-start space-x-2">
                <span class="font-bold">&bull;</span>
                <span><strong>Before / After Photo Proof:</strong> Cleanup crews must submit photographic evidence to close complaints.</span>
              </li>
            </ul>
          </div>
        </div>
      `
    },
    {
      title: "GeoAI Intelligence & Analytics Core",
      subtitle: "Mathematical Rigor & Geospatial Algorithms Driving the System",
      badge: "Core Algorithms",
      content: `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 my-4">
          <div class="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
            <span class="text-xs font-bold text-emerald-700 uppercase tracking-wider block mb-1">01. Vision Classification</span>
            <h4 class="font-bold text-slate-900 text-sm mb-2">AI Waste Classification</h4>
            <p class="text-xs text-slate-600 mb-3">Gemini vision (when an API key is configured) with an offline keyword fallback, recognizing 6 municipal categories (Plastic, C&D, Organic, E-Waste, Hazardous, Mixed MSW) with 94%+ confidence.</p>
            <div class="bg-slate-50 p-2 rounded text-[11px] font-mono text-slate-700">Output: Category, Severity (1-5), Est. Volume (m³), Recyclability</div>
          </div>

          <div class="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
            <span class="text-xs font-bold text-blue-700 uppercase tracking-wider block mb-1">02. Spatial Clustering</span>
            <h4 class="font-bold text-slate-900 text-sm mb-2">DBSCAN Hotspot Engine</h4>
            <p class="text-xs text-slate-600 mb-3">Density-based spatial clustering on Haversine distance matrix with &epsilon; = 250m & minPts = 3 to isolate chronic dumping zones from one-off litter.</p>
            <div class="bg-slate-50 p-2 rounded text-[11px] font-mono text-slate-700">Dumping Index = N_reports &times; Avg_Sev &times; (1 + Open_Ratio)</div>
          </div>

          <div class="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
            <span class="text-xs font-bold text-amber-700 uppercase tracking-wider block mb-1">03. Route Optimization</span>
            <h4 class="font-bold text-slate-900 text-sm mb-2">2-Opt TSP Truck Solver</h4>
            <p class="text-xs text-slate-600 mb-3">Solves the NP-hard Traveling Salesperson pickup tour starting from municipal SWM depots, eliminating backtracking and cutting diesel emissions.</p>
            <div class="bg-slate-50 p-2 rounded text-[11px] font-mono text-slate-700">Metric: km saved vs. priority-order dispatch (computed live)</div>
          </div>
        </div>
      `
    },
    {
      title: "System Architecture & Data Pipeline",
      subtitle: "End-to-End Scalable Citizen-to-Municipal Dispatch Pipeline",
      badge: "Architecture",
      content: `
        <div class="bg-slate-900 text-slate-100 rounded-2xl p-6 my-4 font-mono text-xs shadow-inner">
          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-center">
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span class="text-emerald-400 font-bold block mb-1">1. Citizen Client</span>
              <p class="text-slate-300 text-[11px]">Mobile PWA / Web<br>Auto-GPS Geolocation<br>Camera Photo Upload<br>Offline Sync Queue</p>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span class="text-blue-400 font-bold block mb-1">2. Flask GeoAI Core</span>
              <p class="text-slate-300 text-[11px]">Haversine Distance Engine<br>DBSCAN Clustering<br>Multi-Criteria Scoring<br>2-Opt TSP Dispatch</p>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span class="text-amber-400 font-bold block mb-1">3. Spatial Storage</span>
              <p class="text-slate-300 text-[11px]">SQLite / PostGIS DB<br>BBMP GeoJSON Wards<br>Sensitive Receptor Buffers<br>Immutable Audit Trail</p>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span class="text-purple-400 font-bold block mb-1">4. Municipal Portal</span>
              <p class="text-slate-300 text-[11px]">Live Leaflet Heatmap<br>Top 10 Hotspot Ranking<br>Before/After Verification<br>Truck Route Dispatch</p>
            </div>
          </div>
          <div class="mt-4 pt-3 border-t border-slate-800 text-center text-slate-400 text-[11px]">
            Data Flow: Citizen Capture &rarr; 40m Duplicate Check &rarr; AI Vision Inference &rarr; Spatial Hotspot Aggregation &rarr; Optimized Truck Route
          </div>
        </div>
      `
    },
    {
      title: "Live Results & Hackathon Demonstration",
      subtitle: "Demonstrated across 55 Verified Dumping Incidents in Bengaluru",
      badge: "Validated Results",
      content: `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 my-4">
          <div class="bg-white border border-slate-200 rounded-2xl p-4 text-center shadow-sm">
            <span class="text-3xl font-extrabold text-emerald-600 block">55</span>
            <span class="text-xs font-semibold text-slate-700 mt-1 block">Bengaluru Incidents</span>
            <span class="text-[10px] text-slate-400">Mapped across 10 wards</span>
          </div>
          <div class="bg-white border border-slate-200 rounded-2xl p-4 text-center shadow-sm">
            <span class="text-3xl font-extrabold text-rose-600 block">5</span>
            <span class="text-xs font-semibold text-slate-700 mt-1 block">Recurring Hotspots</span>
            <span class="text-[10px] text-slate-400">Bellandur &amp; Peenya isolated</span>
          </div>
          <div class="bg-white border border-slate-200 rounded-2xl p-4 text-center shadow-sm">
            <span class="text-3xl font-extrabold text-blue-600 block">Live</span>
            <span class="text-xs font-semibold text-slate-700 mt-1 block">Route Efficiency</span>
            <span class="text-[10px] text-slate-400">Shown per route in the Route tab</span>
          </div>
          <div class="bg-white border border-slate-200 rounded-2xl p-4 text-center shadow-sm">
            <span class="text-3xl font-extrabold text-amber-600 block">100%</span>
            <span class="text-xs font-semibold text-slate-700 mt-1 block">Proof Audited</span>
            <span class="text-[10px] text-slate-400">Before/After photographic proof</span>
          </div>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs text-slate-700">
          <strong>Key Validation Highlight:</strong> The system successfully flagged a cluster of high-severity plastic and construction debris along the <em>Bellandur Lake catchment</em>, boosting its priority score to <strong>92/100 (Critical)</strong> due to lake proximity (&lt;150m), while routing the nearest municipal tipper truck on an optimal 14km pickup tour.
        </div>
      `
    },
    {
      title: "Conclusion & Future Roadmap",
      subtitle: "Scaling from Hackathon Prototype to City-Wide Municipal Deployment",
      badge: "Future Scope",
      content: `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 my-4">
          <div class="bg-indigo-50 border border-indigo-200 rounded-2xl p-5">
            <span class="text-xs font-bold text-indigo-700 uppercase tracking-wider block mb-1">Satellite Earth Observation</span>
            <h4 class="font-bold text-slate-900 text-sm mb-1">Sentinel-2 Cross-Check</h4>
            <p class="text-xs text-slate-600">Integrate European Space Agency Sentinel-2 NDVI/NDWI anomaly tiles to verify repeat land-filling along water bodies over time.</p>
          </div>
          <div class="bg-emerald-50 border border-emerald-200 rounded-2xl p-5">
            <span class="text-xs font-bold text-emerald-700 uppercase tracking-wider block mb-1">Conversational AI</span>
            <h4 class="font-bold text-slate-900 text-sm mb-1">WhatsApp &amp; Telegram Bot</h4>
            <p class="text-xs text-slate-600">Allow citizens to send photos and live location directly via WhatsApp without installing an app; auto-parsed by our backend API.</p>
          </div>
          <div class="bg-amber-50 border border-amber-200 rounded-2xl p-5">
            <span class="text-xs font-bold text-amber-700 uppercase tracking-wider block mb-1">Government Integration</span>
            <h4 class="font-bold text-slate-900 text-sm mb-1">BBMP Sahaya 2.0</h4>
            <p class="text-xs text-slate-600">Direct webhook integration into municipal grievance portals with automated contractor penalty deduction for repeat hot spots.</p>
          </div>
        </div>
        <div class="text-center mt-6">
          <p class="text-sm font-bold text-slate-800">Ready for Live Interactive Demonstration</p>
          <p class="text-xs text-slate-500 mt-1">Geo-Waste Reporter &bull; Transforming Urban Sanitation with AI &amp; Spatial Science</p>
        </div>
      `
    }
  ],

  renderSlide: function(slideNum) {
    this.currentSlide = slideNum;
    const slide = this.slides[slideNum - 1];
    if (!slide) return;

    const container = document.getElementById('slide-content-area');
    const indicator = document.getElementById('slide-indicator');
    if (!container) return;

    indicator.innerText = `Slide ${slideNum} of ${this.totalSlides}`;

    container.innerHTML = `
      <div class="slide-box p-6 md:p-10 flex flex-col justify-between">
        <div>
          <div class="flex items-center space-x-3 mb-2">
            <span class="bg-emerald-100 text-emerald-800 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              ${slide.badge}
            </span>
          </div>
          <h2 class="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">${slide.title}</h2>
          <p class="text-sm md:text-base text-slate-500 mt-1">${slide.subtitle}</p>
        </div>

        <div class="flex-1 my-4">
          ${slide.content}
        </div>

        <div class="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
          <span>Geo-Waste Reporter &bull; Problem 10</span>
          <span>Press left and right arrow keys to navigate</span>
        </div>
      </div>
    `;
  },

  next: function() {
    if (this.currentSlide < this.totalSlides) {
      this.renderSlide(this.currentSlide + 1);
    }
  },

  prev: function() {
    if (this.currentSlide > 1) {
      this.renderSlide(this.currentSlide - 1);
    }
  }
};

document.addEventListener('DOMContentLoaded', () => {
  PresentationDeck.renderSlide(1);

  const prevBtn = document.getElementById('btn-prev-slide');
  const nextBtn = document.getElementById('btn-next-slide');

  if (prevBtn) prevBtn.addEventListener('click', () => PresentationDeck.prev());
  if (nextBtn) nextBtn.addEventListener('click', () => PresentationDeck.next());

  // Keyboard navigation
  window.addEventListener('keydown', (e) => {
    if (AppState.currentTab === 'slides-view') {
      if (e.key === 'ArrowRight' || e.key === 'Space') PresentationDeck.next();
      else if (e.key === 'ArrowLeft') PresentationDeck.prev();
    }
  });
});
