/* Sick Day Helper — Panel Logic (Page Router + Sick Day + Mapping + Wizard) */

// --- Shared API helper ---

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}));
    throw new Error(errBody.error || `API ${method} ${path}: ${resp.status}`);
  }
  return resp.json();
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================
// App — Page Router + Sick Day + Mapping
// ============================================================

const App = (() => {
  let currentPage = "sick-day";
  let durationType = "days";

  function navigateTo(page) {
    currentPage = page;

    // Update nav
    document.querySelectorAll(".nav-item").forEach(el => {
      el.classList.toggle("active", el.dataset.page === page);
    });

    // Update pages
    document.querySelectorAll(".page").forEach(el => el.classList.add("hidden"));
    document.getElementById(`page-${page}`).classList.remove("hidden");

    // Load page data
    if (page === "sick-day") loadSickDayPage();
    else if (page === "mapping") loadMappingPage();
    else if (page === "setup") Wizard.init();
  }

  // --- Nav click handlers ---

  function initNav() {
    document.querySelectorAll(".nav-item").forEach(el => {
      el.addEventListener("click", () => navigateTo(el.dataset.page));
    });
  }

  // --- Sick Day Page ---

  async function loadSickDayPage() {
    const loading = document.getElementById("sick-day-loading");
    const content = document.getElementById("sick-day-content");
    loading.classList.remove("hidden");
    content.classList.add("hidden");

    try {
      const [sickDays, mapping] = await Promise.all([
        api("GET", "api/sick-days"),
        api("GET", "api/mapping"),
      ]);

      renderActiveSickDays(sickDays);
      renderDeclareForm(mapping, sickDays);

      loading.classList.add("hidden");
      content.classList.remove("hidden");
    } catch (e) {
      loading.innerHTML = '<p>Failed to load data. Is the add-on running?</p>';
      console.error(e);
    }
  }

  function renderActiveSickDays(sickDays) {
    const container = document.getElementById("active-list");

    if (sickDays.length === 0) {
      container.innerHTML = '<p class="no-active">No active sick days.</p>';
      return;
    }

    container.innerHTML = sickDays.map(sd => {
      const autoBadges = sd.disabled_automations.map(a => {
        const shortName = a.replace("automation.", "").replace(/_/g, " ");
        return `<span class="auto-badge">${esc(shortName)}</span>`;
      }).join("");

      return `
        <div class="sick-card" data-person-id="${esc(sd.person_id)}">
          <div class="sick-card-header">
            <h4>${esc(sd.person_name)}</h4>
            <span class="end-date">Until ${esc(sd.end_date)}</span>
          </div>
          <div class="sick-card-autos">${autoBadges || '<span class="auto-badge">no automations recorded</span>'}</div>
          <div class="sick-card-actions">
            <button class="btn btn-small" onclick="App.showExtendForm('${esc(sd.person_id)}')">Extend</button>
            <button class="btn btn-small btn-danger" onclick="App.cancelSickDay('${esc(sd.person_id)}')">Cancel</button>
          </div>
          <div class="extend-form hidden" id="extend-form-${esc(sd.person_id)}">
            <label>Extend by</label>
            <input type="number" min="1" max="14" value="1" id="extend-days-${esc(sd.person_id)}">
            <label>day(s)</label>
            <button class="btn btn-small" onclick="App.extendSickDay('${esc(sd.person_id)}')">Confirm</button>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderDeclareForm(mapping, sickDays) {
    const noMappingMsg = document.getElementById("no-mapping-msg");
    const declareForm = document.getElementById("declare-form");
    const personSelect = document.getElementById("declare-person");

    const personIds = Object.keys(mapping);
    if (personIds.length === 0) {
      noMappingMsg.classList.remove("hidden");
      declareForm.classList.add("hidden");
      return;
    }

    noMappingMsg.classList.add("hidden");
    declareForm.classList.remove("hidden");

    // Filter out people with already-active sick days
    const activeIds = new Set(sickDays.map(sd => sd.person_id));
    const available = personIds.filter(pid => !activeIds.has(pid));

    if (available.length === 0) {
      personSelect.innerHTML = '<option value="">All people have active sick days</option>';
      document.getElementById("declare-submit").disabled = true;
      return;
    }

    document.getElementById("declare-submit").disabled = false;

    // Build options — resolve friendly names from active sick day data or use entity ID
    personSelect.innerHTML = available.map(pid => {
      // Try to find a friendly name
      const shortName = pid.replace("person.", "").replace(/_/g, " ");
      const capitalized = shortName.replace(/\b\w/g, c => c.toUpperCase());
      return `<option value="${esc(pid)}">${esc(capitalized)}</option>`;
    }).join("");

    // Set tomorrow as default min date
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateInput = document.getElementById("declare-date");
    dateInput.min = tomorrow.toISOString().split("T")[0];
    dateInput.value = tomorrow.toISOString().split("T")[0];
  }

  function setDurationType(type) {
    durationType = type;
    document.querySelectorAll(".toggle-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.type === type);
    });
    document.getElementById("duration-days-group").classList.toggle("hidden", type !== "days");
    document.getElementById("duration-date-group").classList.toggle("hidden", type !== "date");
  }

  async function declareSickDay() {
    const personId = document.getElementById("declare-person").value;
    if (!personId) return;

    const btn = document.getElementById("declare-submit");
    btn.disabled = true;
    btn.textContent = "Submitting...";

    try {
      let durationValue;
      if (durationType === "days") {
        durationValue = parseInt(document.getElementById("declare-days").value);
      } else {
        durationValue = document.getElementById("declare-date").value;
      }

      await api("POST", "api/sick-days/activate", {
        person_id: personId,
        duration_type: durationType,
        duration_value: durationValue,
      });

      // Reload the page
      await loadSickDayPage();
    } catch (e) {
      alert("Failed to declare sick day: " + e.message);
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.textContent = "Submit";
    }
  }

  async function cancelSickDay(personId) {
    if (!confirm("Cancel sick day? Automations will be re-enabled.")) return;

    try {
      await api("POST", "api/sick-days/cancel", { person_id: personId });
      await loadSickDayPage();
    } catch (e) {
      alert("Failed to cancel sick day: " + e.message);
      console.error(e);
    }
  }

  function showExtendForm(personId) {
    const form = document.getElementById(`extend-form-${personId}`);
    form.classList.toggle("hidden");
  }

  async function extendSickDay(personId) {
    const daysInput = document.getElementById(`extend-days-${personId}`);
    const days = parseInt(daysInput.value) || 1;

    try {
      await api("POST", "api/sick-days/extend", {
        person_id: personId,
        duration_type: "days",
        duration_value: days,
      });
      await loadSickDayPage();
    } catch (e) {
      alert("Failed to extend sick day: " + e.message);
      console.error(e);
    }
  }

  // --- Mapping Page ---

  async function loadMappingPage() {
    const loading = document.getElementById("mapping-loading");
    const content = document.getElementById("mapping-content");
    loading.classList.remove("hidden");
    content.classList.add("hidden");

    try {
      const mapping = await api("GET", "api/mapping");
      renderMapping(mapping);
      loading.classList.add("hidden");
      content.classList.remove("hidden");
    } catch (e) {
      loading.innerHTML = '<p>Failed to load mapping.</p>';
      console.error(e);
    }
  }

  function renderMapping(mapping) {
    const container = document.getElementById("mapping-list");
    const personIds = Object.keys(mapping);

    if (personIds.length === 0) {
      container.innerHTML = '<p class="mapping-empty">No mapping configured. Go to Setup to create one.</p>';
      return;
    }

    container.innerHTML = personIds.map(pid => {
      const autos = mapping[pid] || [];
      const shortName = pid.replace("person.", "").replace(/_/g, " ");
      const capitalized = shortName.replace(/\b\w/g, c => c.toUpperCase());

      const badges = autos.length > 0
        ? autos.map(a => {
            const name = a.replace("automation.", "").replace(/_/g, " ");
            return `<span class="auto-badge">${esc(name)}</span>`;
          }).join("")
        : '<span class="auto-badge">no automations</span>';

      return `
        <div class="mapping-card">
          <h4>${esc(capitalized)}</h4>
          <div class="auto-badges">${badges}</div>
        </div>
      `;
    }).join("");
  }

  // --- Boot ---

  function boot() {
    initNav();
    loadSickDayPage();
  }

  document.addEventListener("DOMContentLoaded", boot);

  return {
    navigateTo,
    setDurationType,
    declareSickDay,
    cancelSickDay,
    showExtendForm,
    extendSickDay,
    loadSickDayPage,
  };
})();

// ============================================================
// Wizard — Setup page (all 5 steps, unchanged logic)
// ============================================================

const Wizard = (() => {
  let currentStep = 1;
  let discoveryData = null;
  let selectedPeople = [];
  let mapping = {};
  let initialized = false;

  // --- Step navigation ---

  function goToStep(step) {
    document.querySelectorAll(".step-panel").forEach(el => el.classList.add("hidden"));
    document.getElementById(`step-${step}`).classList.remove("hidden");

    document.querySelectorAll("#progress-bar .step").forEach(el => {
      const s = parseInt(el.dataset.step);
      el.classList.remove("active", "completed");
      if (s === step) el.classList.add("active");
      else if (s < step) el.classList.add("completed");
    });

    currentStep = step;
  }

  // --- Step 1: Welcome ---

  async function init() {
    if (initialized) return;
    initialized = true;

    goToStep(1);

    try {
      const status = await api("GET", "api/status");

      // If wizard already completed, show timestamp instead of running discovery
      if (status.wizard_completed) {
        let stamp = "";
        if (status.wizard_completed_at) {
          const d = new Date(status.wizard_completed_at);
          stamp = d.toLocaleString();
        }

        document.getElementById("welcome-loading").classList.add("hidden");
        document.getElementById("welcome-content").classList.remove("hidden");
        document.getElementById("welcome-new").classList.add("hidden");
        document.getElementById("welcome-existing").classList.remove("hidden");
        document.getElementById("wizard-completed-at").textContent = stamp;
        // Hide stats since we didn't run discovery
        document.querySelector(".stats-grid").classList.add("hidden");
        return;
      }

      // First-time setup — run discovery
      await runDiscovery();
    } catch (e) {
      document.getElementById("welcome-loading").textContent =
        "Failed to load. Is the add-on running?";
      console.error(e);
    }
  }

  async function runDiscovery() {
    document.getElementById("welcome-loading").classList.remove("hidden");
    document.getElementById("welcome-content").classList.add("hidden");
    document.querySelector(".stats-grid").classList.remove("hidden");

    try {
      const discovery = await api("GET", "api/discovery");
      discoveryData = discovery;

      document.getElementById("stat-people").textContent = discovery.counts.people;
      document.getElementById("stat-areas").textContent = discovery.counts.areas;
      document.getElementById("stat-automations").textContent = discovery.counts.automations;
      document.getElementById("stat-time").textContent = discovery.counts.time_triggered;
      document.getElementById("stat-day").textContent = discovery.counts.day_filtered;

      document.getElementById("welcome-existing").classList.add("hidden");
      document.getElementById("welcome-new").classList.remove("hidden");

      document.getElementById("welcome-loading").classList.add("hidden");
      document.getElementById("welcome-content").classList.remove("hidden");
    } catch (e) {
      document.getElementById("welcome-loading").textContent =
        "Failed to load discovery data. Is the add-on running?";
      console.error(e);
    }
  }

  // --- Step 2: People ---

  async function startWizard() {
    // If discovery hasn't been loaded yet (re-run from completed state), run it now
    if (!discoveryData) {
      goToStep(1);
      await runDiscovery();
    }
    renderPeopleStep();
    goToStep(2);
  }

  function renderPeopleStep() {
    const list = document.getElementById("people-list");
    const suggested = discoveryData.suggested_mapping || {};
    list.innerHTML = "";

    discoveryData.people.forEach(person => {
      const hasSuggestion = (suggested[person.entity_id] || []).length > 0;
      const item = document.createElement("div");
      item.className = "checkbox-item";
      item.innerHTML = `
        <input type="checkbox" id="person-${person.entity_id}"
               value="${person.entity_id}" ${hasSuggestion ? "checked" : ""}>
        <label for="person-${person.entity_id}">
          ${esc(person.friendly_name)}
          <span class="entity-id">${esc(person.entity_id)}</span>
        </label>
      `;
      list.appendChild(item);
    });
  }

  function submitPeople() {
    selectedPeople = [];
    document.querySelectorAll("#people-list input:checked").forEach(cb => {
      selectedPeople.push(cb.value);
    });

    if (selectedPeople.length === 0) {
      alert("Please select at least one person.");
      return;
    }

    renderAreasStep();
    goToStep(3);
  }

  // --- Step 3: Areas ---

  function renderAreasStep() {
    const container = document.getElementById("areas-list");
    container.innerHTML = "";

    discoveryData.areas.forEach(area => {
      if (area.automation_ids.length === 0) return;

      const card = document.createElement("div");
      card.className = "area-card";

      const autoList = area.automation_ids.map(aid => {
        const auto = discoveryData.automations.find(a => a.entity_id === aid);
        const name = auto ? auto.friendly_name : aid;
        const badges = getBadges(auto);
        return `<li>${esc(name)}${badges}</li>`;
      }).join("");

      const bestMatches = findBestPeopleForArea(area);
      const personCheckboxes = selectedPeople.map(pid => {
        const person = discoveryData.people.find(p => p.entity_id === pid);
        const name = esc(person ? person.friendly_name : pid);
        const checked = bestMatches.includes(pid) ? "checked" : "";
        return `<label class="person-check">
          <input type="checkbox" data-area-id="${area.area_id}" value="${pid}" ${checked}>
          ${name}
        </label>`;
      }).join("");

      card.innerHTML = `
        <div class="area-card-header">
          <h4>${esc(area.name)}</h4>
          <span class="count">${area.automation_ids.length} automation(s)</span>
        </div>
        <div class="person-checks">${personCheckboxes}</div>
        <ul class="area-automations">${autoList}</ul>
      `;

      container.appendChild(card);
    });

    // Unassigned automations
    const unassigned = discoveryData.unassigned_automations || [];
    const unassignedSection = document.getElementById("unassigned-section");
    const unassignedList = document.getElementById("unassigned-list");

    if (unassigned.length > 0) {
      unassignedSection.classList.remove("hidden");
      unassignedList.innerHTML = "";

      unassigned.forEach(aid => {
        const auto = discoveryData.automations.find(a => a.entity_id === aid);
        const name = auto ? auto.friendly_name : aid;
        const badges = getBadges(auto);
        const bestMatches = findBestPeopleForAutomation(aid);

        const personCheckboxes = selectedPeople.map(pid => {
          const person = discoveryData.people.find(p => p.entity_id === pid);
          const pname = esc(person ? person.friendly_name : pid);
          const checked = bestMatches.includes(pid) ? "checked" : "";
          return `<label class="person-check">
            <input type="checkbox" data-unassigned-auto="${aid}" value="${pid}" ${checked}>
            ${pname}
          </label>`;
        }).join("");

        const item = document.createElement("div");
        item.className = "area-card";
        item.style.padding = "10px 16px";
        item.innerHTML = `
          <div class="unassigned-auto-row">
            <span class="unassigned-auto-name">${esc(name)}${badges}</span>
            <div class="person-checks">${personCheckboxes}</div>
          </div>
        `;

        unassignedList.appendChild(item);
      });
    } else {
      unassignedSection.classList.add("hidden");
    }
  }

  function findBestPeopleForArea(area) {
    const suggested = discoveryData.suggested_mapping || {};
    const matches = [];
    for (const pid of selectedPeople) {
      const autoIds = suggested[pid] || [];
      const overlap = area.automation_ids.filter(a => autoIds.includes(a));
      if (overlap.length > 0) matches.push(pid);
    }
    return matches;
  }

  function findBestPeopleForAutomation(autoId) {
    const suggested = discoveryData.suggested_mapping || {};
    const matches = [];
    for (const pid of selectedPeople) {
      if ((suggested[pid] || []).includes(autoId)) matches.push(pid);
    }
    return matches;
  }

  function submitAreas() {
    mapping = {};
    selectedPeople.forEach(pid => { mapping[pid] = []; });

    document.querySelectorAll("[data-area-id]:checked").forEach(cb => {
      const areaId = cb.dataset.areaId;
      const personId = cb.value;

      const area = discoveryData.areas.find(a => a.area_id === areaId);
      if (area) {
        area.automation_ids.forEach(aid => {
          if (!mapping[personId].includes(aid)) {
            mapping[personId].push(aid);
          }
        });
      }
    });

    document.querySelectorAll("[data-unassigned-auto]:checked").forEach(cb => {
      const autoId = cb.dataset.unassignedAuto;
      const personId = cb.value;
      if (!mapping[personId].includes(autoId)) {
        mapping[personId].push(autoId);
      }
    });

    for (const pid of selectedPeople) {
      mapping[pid].sort();
    }

    renderReviewStep();
    goToStep(4);
  }

  // --- Step 4: Review ---

  function renderReviewStep() {
    const container = document.getElementById("review-list");
    container.innerHTML = "";

    selectedPeople.forEach(pid => {
      const person = discoveryData.people.find(p => p.entity_id === pid);
      const personName = person ? person.friendly_name : pid;
      const automations = mapping[pid] || [];

      const section = document.createElement("div");
      section.className = "review-person";

      let autoHtml = "";
      if (automations.length === 0) {
        autoHtml = '<p class="subtext" style="padding:8px 12px">No automations assigned.</p>';
      } else {
        autoHtml = automations.map(aid => {
          const auto = discoveryData.automations.find(a => a.entity_id === aid);
          const name = auto ? auto.friendly_name : aid;
          const badges = getBadges(auto);
          return `
            <div class="review-automation">
              <label>${esc(name)}${badges}</label>
              <button class="remove-btn" onclick="Wizard.removeAutomation('${pid}', '${aid}')" title="Remove">&times;</button>
            </div>
          `;
        }).join("");
      }

      section.innerHTML = `<h4>${esc(personName)}</h4>${autoHtml}`;
      container.appendChild(section);
    });

    updateAddAutomationRow();
  }

  function updateAddAutomationRow() {
    const allMapped = new Set();
    for (const autos of Object.values(mapping)) {
      autos.forEach(a => allMapped.add(a));
    }

    const unmapped = discoveryData.automations.filter(a => !allMapped.has(a.entity_id));
    const addRow = document.getElementById("add-automation-row");

    if (unmapped.length > 0 && selectedPeople.length > 0) {
      addRow.classList.remove("hidden");

      const personSelect = document.getElementById("add-auto-person");
      personSelect.innerHTML = selectedPeople.map(pid => {
        const p = discoveryData.people.find(pp => pp.entity_id === pid);
        return `<option value="${pid}">${esc(p ? p.friendly_name : pid)}</option>`;
      }).join("");

      const autoSelect = document.getElementById("add-auto-automation");
      autoSelect.innerHTML = unmapped.map(a =>
        `<option value="${a.entity_id}">${esc(a.friendly_name)}</option>`
      ).join("");
    } else {
      addRow.classList.add("hidden");
    }
  }

  function removeAutomation(personId, autoId) {
    mapping[personId] = (mapping[personId] || []).filter(a => a !== autoId);
    renderReviewStep();
  }

  function addAutomation() {
    const personId = document.getElementById("add-auto-person").value;
    const autoId = document.getElementById("add-auto-automation").value;
    if (!personId || !autoId) return;

    if (!mapping[personId]) mapping[personId] = [];
    if (!mapping[personId].includes(autoId)) {
      mapping[personId].push(autoId);
      mapping[personId].sort();
    }
    renderReviewStep();
  }

  async function submitReview() {
    const btn = document.querySelector("#step-4 .btn-primary");
    btn.disabled = true;
    btn.textContent = "Saving...";

    try {
      await api("POST", "api/wizard/complete", { mapping });
      renderCompleteStep();
      goToStep(5);
    } catch (e) {
      alert("Failed to save mapping: " + e.message);
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.textContent = "Save Mapping";
    }
  }

  // --- Step 5: Complete ---

  function renderCompleteStep() {
    const container = document.getElementById("complete-summary");

    let html = '<p class="info-box" style="margin-bottom:16px">Your mapping has been saved. Sick Day Helper is now ready to use.</p>';

    selectedPeople.forEach(pid => {
      const person = discoveryData.people.find(p => p.entity_id === pid);
      const personName = person ? person.friendly_name : pid;
      const autos = mapping[pid] || [];

      html += `<div class="summary-person"><h4>${esc(personName)}</h4><ul>`;
      if (autos.length === 0) {
        html += "<li>No automations</li>";
      } else {
        autos.forEach(aid => {
          const auto = discoveryData.automations.find(a => a.entity_id === aid);
          html += `<li>${esc(auto ? auto.friendly_name : aid)}</li>`;
        });
      }
      html += "</ul></div>";
    });

    container.innerHTML = html;
  }

  // --- Skip (auto-mapping) ---

  async function skipToAutoMapping() {
    const suggested = discoveryData.suggested_mapping || {};
    mapping = {};
    selectedPeople = [];

    for (const [pid, autos] of Object.entries(suggested)) {
      selectedPeople.push(pid);
      mapping[pid] = autos;
    }

    const btn = document.querySelector("#welcome-new .btn-secondary");
    btn.disabled = true;
    btn.textContent = "Saving...";

    try {
      await api("POST", "api/wizard/complete", { mapping });
      renderCompleteStep();
      goToStep(5);
    } catch (e) {
      alert("Failed to save mapping: " + e.message);
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.textContent = "Skip (use auto-mapping)";
    }
  }

  // --- Reset wizard ---

  async function resetWizard() {
    try {
      await api("POST", "api/wizard/reset");
      initialized = false;
      discoveryData = null;
      await init();
    } catch (e) {
      alert("Failed to reset wizard: " + e.message);
      console.error(e);
    }
  }

  // --- Helpers ---

  function getBadges(auto) {
    if (!auto || !auto.classification) return "";
    let b = "";
    if (auto.classification.time_triggered) b += '<span class="badge badge-time">time</span>';
    if (auto.classification.day_filtered) b += '<span class="badge badge-day">day</span>';
    return b;
  }

  return {
    init,
    goToStep,
    startWizard,
    submitPeople,
    submitAreas,
    submitReview,
    removeAutomation,
    addAutomation,
    skipToAutoMapping,
    resetWizard,
  };
})();
