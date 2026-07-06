// Configuration Constants
const BACKEND_HOST = "http://127.0.0.1:8501";
const APP_NAME = "src";
const USER_ID = "system";

// Application State Variables
let currentSessionId = "";
let isScanning = false;
let accumulatedState = {
  product_name: "Unknown Product",
  category: "other",
  verdict: "UNKNOWN",
  explanation: "No safety details retrieved yet.",
  chemicals_of_concern: [],
  sources: [],
  alternative: {}
};

// DOM Elements
const scanForm = document.getElementById("scan-form");
const queryInput = document.getElementById("query-input");
const loadingPanel = document.getElementById("loading-panel");
const loadingTitle = document.getElementById("loading-title");
const loadingStatus = document.getElementById("loading-status");
const hitlCategoryPanel = document.getElementById("hitl-category-panel");
const vibeDiffModal = document.getElementById("vibe-diff-modal");
const verdictPanel = document.getElementById("verdict-panel");

// Helper: Generate UUID for sessions
function generateUUID() {
  return 'sess-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now().toString(36);
}

// 1. Initialize session on backend
async function initializeSession(sessionId) {
  const url = `${BACKEND_HOST}/apps/${APP_NAME}/users/${USER_ID}/sessions`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId })
  });
  if (!response.ok) {
    throw new Error(`Failed to initialize session: ${response.statusText}`);
  }
  return response.json();
}

// 2. Main Scan submission handler
scanForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (isScanning) return;

  const query = queryInput.value.trim();
  if (!query) return;

  // Reset states
  isScanning = true;
  currentSessionId = generateUUID();
  accumulatedState = {
    product_name: query,
    category: "other",
    verdict: "UNKNOWN",
    explanation: "",
    chemicals_of_concern: [],
    sources: [],
    alternative: {}
  };

  // UI Reset
  verdictPanel.classList.add("hidden");
  hitlCategoryPanel.classList.add("hidden");
  vibeDiffModal.classList.add("hidden");
  loadingPanel.classList.remove("hidden");
  updateLoadingState("Initializing Scanner...", "Creating session connection on server...");

  try {
    // Acknowledge session creation
    await initializeSession(currentSessionId);
    
    // Construct payload
    const payload = {
      app_name: APP_NAME,
      user_id: USER_ID,
      session_id: currentSessionId,
      new_message: {
        role: "user",
        parts: [{ text: query }]
      }
    };
    
    // Run SSE Stream
    await runStreamRequest(payload);
  } catch (error) {
    console.error("Scan error:", error);
    showError(error.message);
  } finally {
    isScanning = false;
  }
});

// 3. Robust Stream Reader for Server-Sent Events (SSE) via POST
async function runStreamRequest(payload) {
  const url = `${BACKEND_HOST}/run_sse`;
  
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`SSE request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // Save incomplete last line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data:")) {
        try {
          const eventData = JSON.parse(trimmed.substring(5).trim());
          handleAgentEvent(eventData);
        } catch (e) {
          console.warn("Failed to parse SSE JSON chunk:", e);
          try {
            JSON.parse(trimmed.substring(5).trim());
            alert("Error in handleAgentEvent: " + e.message + "\nStack: " + e.stack);
          } catch (jsonErr) {
            // Ignore incomplete JSON chunks
          }
        }
      }
    }
  }
  
  // Finish processing when stream closes
  loadingPanel.classList.add("hidden");
  if (hitlCategoryPanel.classList.contains("hidden") && vibeDiffModal.classList.contains("hidden")) {
    renderVerdictCard();
  }
}

// 4. Handle incoming ADK agent events from stream
function handleAgentEvent(event) {
  // Update status based on node execution path
  const nodeInfo = event.nodeInfo || event.node_info;
  if (nodeInfo && nodeInfo.path) {
    const path = nodeInfo.path.toLowerCase();
    if (path.includes("gather_evidence")) {
      updateLoadingState("Gathering Evidence...", "Checking Open Facts databases & Google search...");
    } else if (path.includes("identify_product")) {
      updateLoadingState("Identifying Product...", "Analyzing product ingredients and category fields...");
    } else if (path.includes("get_pubchem_facts")) {
      updateLoadingState("Querying PubChem GHS...", "Fetching chemical safety hazard annotation records...");
    } else if (path.includes("safety_evaluator")) {
      updateLoadingState("Evaluating Safety...", "Analyzing ingredients against specialist toxicology rules...");
    } else if (path.includes("hallucination_guard")) {
      updateLoadingState("Enforcing Guardrails...", "Auditing cited chemical claims against database ingredients...");
    }
  }

  // Handle State Deltas and Final Output keys
  const actions = event.actions || {};
  const delta = (actions.stateDelta || actions.state_delta) ? (actions.stateDelta || actions.state_delta) : {};
  const output = (event.output && typeof event.output === 'object') ? event.output : {};
  
  // Merge delta and output for parsing
  const data = { ...delta, ...output };
  
  if (Object.keys(data).length > 0) {
    const productName = data.productName || data.product_name;
    if (productName) accumulatedState.product_name = productName;
    if (data.category) accumulatedState.category = data.category;
    if (data.ingredients) accumulatedState.ingredients = data.ingredients;
    
    // Parse nested verdict_data
    const verdictData = data.verdictData || data.verdict_data;
    if (verdictData) {
      accumulatedState.verdict = verdictData.verdict || "UNKNOWN";
      accumulatedState.explanation = verdictData.explanation || "";
      const chems = verdictData.chemicalsOfConcern || verdictData.chemicals_of_concern || [];
      accumulatedState.chemicals_of_concern = chems;
      accumulatedState.sources = verdictData.sources || [];
    }
    
    if (data.verdict) accumulatedState.verdict = data.verdict;
    if (data.explanation) accumulatedState.explanation = data.explanation;
    
    const chemicalsOfConcern = data.chemicalsOfConcern || data.chemicals_of_concern;
    if (chemicalsOfConcern) accumulatedState.chemicals_of_concern = chemicalsOfConcern;
    
    if (data.sources) accumulatedState.sources = data.sources;
    if (data.alternative) accumulatedState.alternative = data.alternative;
    
    const imageUrl = data.imageUrl || data.image_url;
    if (imageUrl) accumulatedState.image_url = imageUrl;
  }

  // Handle Human-in-the-loop (HITL) Interruptions
  const tools = event.longRunningToolIds || event.long_running_tool_ids;
  if (tools && Array.isArray(tools)) {
    if (tools.includes("category_clarification")) {
      // Pause scan and show category clarify options
      loadingPanel.classList.add("hidden");
      hitlCategoryPanel.classList.remove("hidden");
      lucide.createIcons();
    } else if (tools.includes("vibe_diff_approval")) {
      // Pause scan and show Vibe Diff modal
      loadingPanel.classList.add("hidden");
      showVibeDiffModal(event);
    }
  }
}

// 5. Update Loading Indicators
function updateLoadingState(title, text) {
  loadingTitle.textContent = title;
  loadingStatus.textContent = text;
}

// 6. Display Vibe Diff Audit Modal
function showVibeDiffModal(event) {
  try {
    const parts = event.content?.parts || [];
    let auditMessage = "";
    for (const part of parts) {
      if (part.function_call?.args?.message) {
        auditMessage = part.function_call.args.message;
      }
    }

    // Parse raw text message and render inside modal split panes
    const rawFactsEl = document.getElementById("raw-facts-content");
    const draftExplanationEl = document.getElementById("draft-verdict-explanation");
    const draftChemicalsEl = document.getElementById("draft-verdict-chemicals");
    const draftBadge = document.getElementById("draft-verdict-badge");

    const verdict = accumulatedState.verdict || "UNKNOWN";
    draftBadge.textContent = verdict;
    draftBadge.className = `draft-verdict-badge ${verdict.toLowerCase()}`;
    draftExplanationEl.textContent = accumulatedState.explanation || "No explanation provided.";
    
    const chems = accumulatedState.chemicals_of_concern || [];
    draftChemicalsEl.textContent = Array.isArray(chems) ? chems.join(", ") : String(chems);
    
    // Format raw facts directly from state
    const rawFacts = {
      product_name: accumulatedState.product_name,
      ingredients: accumulatedState.ingredients || [],
      database: "PubChem GHS & Open Facts",
      pubchem_hazards: {}
    };
    rawFactsEl.textContent = JSON.stringify(rawFacts, null, 2);

    vibeDiffModal.classList.remove("hidden");
    lucide.createIcons();
  } catch (err) {
    console.error("Error in showVibeDiffModal:", err);
    alert("Error in showVibeDiffModal: " + err.message + "\nStack: " + err.stack);
    // Fallback: force modal display so workflow doesn't lock up
    vibeDiffModal.classList.remove("hidden");
  }
}

// 7. Render Final Safety Report Card
function renderVerdictCard() {
  const nameEl = document.getElementById("verdict-product-name");
  const catEl = document.getElementById("verdict-category");
  const badgeEl = document.getElementById("verdict-badge");
  const explanationEl = document.getElementById("verdict-explanation");
  const chemicalsSec = document.getElementById("chemicals-section");
  const chemicalsContainer = document.getElementById("verdict-chemicals-container");
  const altSec = document.getElementById("alternative-section");
  const altNameEl = document.getElementById("alt-product-name");
  const altRetailerEl = document.getElementById("alt-retailer");
  const altPriceEl = document.getElementById("alt-price");
  const altBuyBtn = document.getElementById("alt-buy-btn");
  const citationsList = document.getElementById("verdict-citations-list");

  // Set basic details
  nameEl.textContent = accumulatedState.product_name;
  catEl.textContent = accumulatedState.category;
  
  // Set product image or neutral category-based fallback icon
  const categoryIcons = {
    food: "apple",
    skincare: "droplet",
    cookware: "chef-hat",
    cleaning: "brush",
    other: "package"
  };
  
  const imgEl = document.getElementById("verdict-product-image");
  const iconPlaceholder = document.getElementById("verdict-product-icon");
  const iconTag = document.getElementById("placeholder-icon-tag");
  const currentCat = (accumulatedState.category || "other").toLowerCase();
  
  // Set fallback icon attribute
  const targetIcon = categoryIcons[currentCat] || categoryIcons.other;
  iconTag.setAttribute("data-lucide", targetIcon);
  
  const imageUrl = accumulatedState.image_url;
  if (imageUrl) {
    imgEl.src = imageUrl;
    imgEl.onload = () => {
      imgEl.classList.remove("hidden");
      iconPlaceholder.classList.add("hidden");
    };
    imgEl.onerror = () => {
      imgEl.classList.add("hidden");
      iconPlaceholder.classList.remove("hidden");
    };
  } else {
    imgEl.classList.add("hidden");
    iconPlaceholder.classList.remove("hidden");
  }
  
  // Set badge styles
  const verd = accumulatedState.verdict.toUpperCase();
  badgeEl.textContent = verd;
  badgeEl.className = `verdict-status-badge ${verd.toLowerCase()}`;
  
  // Set Safety Explanation
  explanationEl.innerHTML = formatMarkdown(accumulatedState.explanation || "No safety evaluation details found.");

  // Set Chemicals of Concern
  chemicalsContainer.innerHTML = "";
  if (accumulatedState.chemicals_of_concern && accumulatedState.chemicals_of_concern.length > 0) {
    chemicalsSec.classList.remove("hidden");
    accumulatedState.chemicals_of_concern.forEach(chem => {
      const badge = document.createElement("span");
      badge.className = "chemical-badge";
      badge.textContent = chem;
      chemicalsContainer.appendChild(badge);
    });
  } else {
    chemicalsSec.classList.add("hidden");
  }

  // Set Cleaner Alternative Card
  if (accumulatedState.alternative && accumulatedState.alternative.alternative_product) {
    const alt = accumulatedState.alternative;
    altSec.classList.remove("hidden");
    altNameEl.textContent = alt.alternative_product;
    altRetailerEl.textContent = alt.retailer || "Target";
    altPriceEl.textContent = alt.price ? `$${alt.price}` : "";
    altBuyBtn.href = alt.buy_link || "#";
  } else {
    altSec.classList.add("hidden");
  }

  // Set Citations
  citationsList.innerHTML = "";
  if (accumulatedState.sources && accumulatedState.sources.length > 0) {
    accumulatedState.sources.forEach(source => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = source.url;
      a.target = "_blank";
      a.innerHTML = `<i data-lucide="external-link" style="width:1rem;height:1rem;display:inline-block;vertical-align:middle;margin-right:2px;"></i> ${source.name}`;
      li.appendChild(a);
      citationsList.appendChild(li);
    });
  } else {
    // Show a default PubChem GHS link if none provided
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = "https://pubchem.ncbi.nlm.nih.gov/";
    a.target = "_blank";
    a.innerHTML = `<i data-lucide="external-link" style="width:1rem;height:1rem;display:inline-block;vertical-align:middle;margin-right:2px;"></i> PubChem GHS Database`;
    li.appendChild(a);
    citationsList.appendChild(li);
  }

  verdictPanel.classList.remove("hidden");
  lucide.createIcons();
}

// Helper: Quick simple markdown-to-html converter for explanation formatting
function formatMarkdown(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

// 8. Handle HITL Category overridden choices
document.querySelectorAll(".btn-option").forEach(btn => {
  btn.addEventListener("click", async (e) => {
    const category = e.target.closest("button").dataset.category;
    hitlCategoryPanel.classList.add("hidden");
    loadingPanel.classList.remove("hidden");
    updateLoadingState("Overriding Category...", `Setting category to '${category}' and resuming scanner...`);

    let finalAnswer = category;
    if (category === "none") finalAnswer = "none of these";

    // Build resumption payload containing the category override
    const payload = {
      app_name: APP_NAME,
      user_id: USER_ID,
      session_id: currentSessionId,
      new_message: {
        role: "user",
        parts: [{
          function_response: {
            id: "category_clarification",
            name: "adk_request_input",
            response: {
              result: finalAnswer
            }
          }
        }]
      }
    };

    try {
      await runStreamRequest(payload);
    } catch (err) {
      showError(err.message);
    }
  });
});

// 9. Handle HITL Vibe Diff Approval choices
document.getElementById("btn-approve").addEventListener("click", () => submitVibeDiffResponse("True"));
document.getElementById("btn-reject").addEventListener("click", () => submitVibeDiffResponse("False"));

async function submitVibeDiffResponse(approvedStatus) {
  vibeDiffModal.classList.add("hidden");
  loadingPanel.classList.remove("hidden");
  updateLoadingState("Submitting Audit...", `Human audit returned: ${approvedStatus}. Resuming workflow...`);

  // Build resumption payload for vibe diff approval
  const payload = {
    app_name: APP_NAME,
    user_id: USER_ID,
    session_id: currentSessionId,
    new_message: {
      role: "user",
      parts: [{
        function_response: {
          id: "vibe_diff_approval",
          name: "adk_request_input",
          response: {
            result: approvedStatus
          }
        }
      }]
    }
  };

  try {
    await runStreamRequest(payload);
  } catch (err) {
    showError(err.message);
  }
}

// Show error utility
function showError(msg) {
  loadingPanel.classList.add("hidden");
  verdictPanel.classList.remove("hidden");
  document.getElementById("verdict-product-name").textContent = "Scan Failure";
  document.getElementById("verdict-category").textContent = "ERROR";
  document.getElementById("verdict-badge").textContent = "UNKNOWN";
  document.getElementById("verdict-badge").className = "verdict-status-badge unknown";
  document.getElementById("verdict-explanation").textContent = `An error occurred during scanning: ${msg}. Please refresh and try again.`;
  document.getElementById("chemicals-section").classList.add("hidden");
  document.getElementById("alternative-section").classList.add("hidden");
}
