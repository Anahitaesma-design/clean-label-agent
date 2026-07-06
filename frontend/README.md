# Clean Label Consumer UI Dashboard

This is the lightweight, premium consumer-facing web application for the Clean Label Safety Scanner. It communicates directly with your running ADK/FastAPI agent server.

## 🚀 How to Run and Test

### Step 1: Ensure your ADK Server is running
Make sure the ADK backend server is running on port `8501` with CORS origin wildcard permissions enabled:
```bash
python -m google.adk.cli web src/ --port 8501 --allow_origins=*
```

### Step 2: Open the Consumer UI
Simply open the `consumer.html` file in any modern web browser:
* Double-click the file [frontend/consumer.html](file:///C:/Dev/Koggle%205-Day/Capstone-Final-Project/clean-label-agent/frontend/consumer.html) in your file explorer.
* Or open it using a local HTTP server if preferred:
  ```bash
  # Option A: using npx (Node.js)
  npx serve frontend/
  
  # Option B: using Python
  python -m http.server 8000 --directory frontend/
  ```

---

## 🧪 Verified Scenarios to Test in the UI

1. **Barcode `716786866133` (Purex detergent)**:
   * **Behavior**: Scans automatically with zero human-in-the-loop prompts.
   * **Result**: Because no ingredient details exist in the database, it falls back to a clean, consumer-friendly `UNKNOWN` safety card.

2. **Text Search `"classic teflon pan"`**:
   * **Behavior**: Scans raw facts, prompts you with a **Vibe Diff Audit Modal** (confirming details side-by-side).
   * **Result**: Displays `UNSAFE` along with a **Suggested Cleaner Alternative** card containing a direct Target purchase buy link.

3. **Barcode `715785855133` (Lucas Polvos Mango - Low Category Confidence)**:
   * **Behavior**: Suspends scan execution and slides down a **Category Clarification** panel.
   * **Result**: Click **[Food / Edible]**—the scanner immediately resumes, fetches safety profiles, and renders a `SAFE` verdict card.
