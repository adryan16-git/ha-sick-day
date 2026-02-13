/* Sick Day Helper — Setup Wizard Logic */

const Wizard = (() => {
  let currentStep = 1;
  let discoveryData = null;
  let selectedPeople = [];
  let areaAssignments = {};   // area_id -> person entity_id
  let unassignedAssignments = {}; // automation entity_id -> person entity_id
  let mapping = {};           // person entity_id -> [automation entity_ids]

  // --- API helpers ---

  async function api(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(path, opts);
    if (!resp.ok) throw new Error(`API ${method} ${path}: ${resp.status}`);
    return resp.json();
  }

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
    goToStep(1);

    try {
      const [status, discovery] = await Promise.all([
        api("GET", "api/status"),
        api("GET", "api/discovery"),
      ]);

      discoveryData = discovery;

      // Populate stats
      document.getElementById("stat-people").textContent = discovery.counts.people;
      document.getElementById("stat-areas").textContent = discovery.counts.areas;
      document.getElementById("stat-automations").textContent = discovery.counts.automations;
      document.getElementById("stat-time").textContent = discovery.counts.time_triggered;
      document.getElementById("stat-day").textContent = discovery.counts.day_filtered;

      // Show existing or new
      if (status.wizard_completed) {
        document.getElementById("welcome-existing").classList.remove("hidden");
        document.getElementById("welcome-new").classList.add("hidden");
      } else {
        document.getElementById("welcome-existing").classList.add("hidden");
        document.getElementById("welcome-new").classList.remove("hidden");
      }

      document.getElementById("welcome-loading").classList.add("hidden");
      document.getElementById("welcome-content").classList.remove("hidden");
    } catch (e) {
      document.getElementById("welcome-loading").textContent =
        "Failed to load discovery data. Is the add-on running?";
      console.error(e);
    }
  }

  // --- Step 2: People ---

  function startWizard() {
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

    const personOptions = selectedPeople.map(pid => {
      const person = discoveryData.people.find(p => p.entity_id === pid);
      return `<option value="${pid}">${esc(person ? person.friendly_name : pid)}</option>`;
    }).join("");

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

      card.innerHTML = `
        <div class="area-card-header">
          <h4>${esc(area.name)}</h4>
          <span class="count">${area.automation_ids.length} automation(s)</span>
        </div>
        <select data-area-id="${area.area_id}">
          <option value="">(unassigned)</option>
          ${personOptions}
        </select>
        <ul class="area-automations">${autoList}</ul>
      `;

      // Pre-select based on suggested mapping
      const select = card.querySelector("select");
      const bestMatch = findBestPersonForArea(area);
      if (bestMatch) select.value = bestMatch;

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

        const item = document.createElement("div");
        item.className = "area-card";
        item.style.padding = "10px 16px";
        item.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px">
            <span style="flex:1">${esc(name)}${badges}</span>
            <select data-unassigned-auto="${aid}" style="width:auto;min-width:140px">
              <option value="">(skip)</option>
              ${personOptions}
            </select>
          </div>
        `;

        // Pre-select
        const select = item.querySelector("select");
        const bestPerson = findBestPersonForAutomation(aid);
        if (bestPerson) select.value = bestPerson;

        unassignedList.appendChild(item);
      });
    } else {
      unassignedSection.classList.add("hidden");
    }
  }

  function findBestPersonForArea(area) {
    const suggested = discoveryData.suggested_mapping || {};
    for (const pid of selectedPeople) {
      const autoIds = suggested[pid] || [];
      const overlap = area.automation_ids.filter(a => autoIds.includes(a));
      if (overlap.length > 0) return pid;
    }
    return "";
  }

  function findBestPersonForAutomation(autoId) {
    const suggested = discoveryData.suggested_mapping || {};
    for (const pid of selectedPeople) {
      if ((suggested[pid] || []).includes(autoId)) return pid;
    }
    return "";
  }

  function submitAreas() {
    // Collect area assignments
    mapping = {};
    selectedPeople.forEach(pid => { mapping[pid] = []; });

    document.querySelectorAll("[data-area-id]").forEach(select => {
      const areaId = select.dataset.areaId;
      const personId = select.value;
      if (!personId) return;

      const area = discoveryData.areas.find(a => a.area_id === areaId);
      if (area) {
        area.automation_ids.forEach(aid => {
          if (!mapping[personId].includes(aid)) {
            mapping[personId].push(aid);
          }
        });
      }
    });

    // Collect unassigned automation assignments
    document.querySelectorAll("[data-unassigned-auto]").forEach(select => {
      const autoId = select.dataset.unassignedAuto;
      const personId = select.value;
      if (!personId) return;
      if (!mapping[personId].includes(autoId)) {
        mapping[personId].push(autoId);
      }
    });

    // Sort each person's automations
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

    // Show add-automation row if there are unmapped automations
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

  function esc(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // --- Boot ---
  init();

  return {
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
