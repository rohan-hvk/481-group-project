# Trading Visualization Project README

## Overview
This project visualizes trading/market data (order book + options Greeks) using an interactive HTML dashboard.

The system has two main parts:
1. **Data processing (Python)**
2. **Visualization (HTML/JavaScript)**

---

## File Types Explained

### 1. Standalone HTML
- File: `trading_greeks_explorer_standalone.html`
- ✅ Easiest to use
- ✅ No setup required
- Contains **all data embedded inside the file**

**How to use:**
- Just double-click and open in a browser

**When to use:**
- Demos / presentations
- Quick viewing
- When you don’t want to deal with file paths or servers

---

### 2. Non-Standalone HTML
- File: `trading_greeks_explorer.html`
- Requires: `processed_trading_data.json`

**How it works:**
- HTML loads data from the JSON file

**How to run:**
- Option 1: Open with Live Server (VSCode recommended)
- Option 2:
  ```bash
  python -m http.server
  ```
  Then go to `http://localhost:8000`

**When to use:**
- When working with updated data
- When files are large
- When separating code and data is preferred

---

### 3. Processed JSON
- File: `processed_trading_data.json`

This is a **cleaned + compressed version** of the raw dataset.

**Why it exists:**
- Raw data is too large and complex for direct browser use
- This file is optimized for fast visualization

---

### 4. Build Script (Python)
- File: `build_viz.py`

This script converts raw trading data into the processed JSON format.

---

## When to Use the Build Script

Use `build_viz.py` ONLY when:
- You have a **new dataset**
- You updated the raw JSON
- You want to regenerate visualization data

Do NOT use it when:
- You already have `processed_trading_data.json`
- You are just viewing the visualization

---

## How to Use the Build Script

1. Place your raw JSON file in your project folder
2. Open `build_viz.py`
3. Update the file path:

```python
SRC = Path("your_file_name.json")
```

4. Run:
```bash
python build_viz.py
```

5. This generates:
```
processed_trading_data.json
```

6. Refresh your HTML visualization

---

## Important Notes About Data

### Expected Data Structure
Your dataset should include fields like:
- `timestamp`
- `future_strike` or strike price
- `Side` (bid/ask)
- `MBO` (size/volume)
- Greeks:
  - `delta`
  - `gamma`
  - `vega`
  - `vanna`
  - `vomma`

If your dataset differs, the build script may need adjustments.

---

### Why We Process Data First

Raw datasets are often:
- Too large (slow in browser)
- Too granular (tick-level)
- Not structured for visualization

The build script:
- Aggregates data by timestamp + strike
- Creates lighter datasets
- Makes charts fast and responsive

---

## Common Issues & Fixes

### 1. "File not found" error in Python

Cause:
- Wrong file path

Fix:
- Update path in `build_viz.py` to your local file

---

### 2. Visualization not loading data

Cause:
- Opening HTML directly without a server

Fix:
- Use Live Server OR:
  ```bash
  python -m http.server
  ```

---

### 3. Changes not appearing

Fix:
- Refresh browser
- Make sure JSON file updated

---

## Recommended Workflow

### Normal Use (No Data Changes)
- Open **standalone HTML**

### Working With Data
1. Update raw dataset
2. Run build script
3. Use non-standalone HTML
4. Refresh browser

---

## Summary

- Standalone HTML = easiest, no setup
- Non-standalone = flexible, uses JSON
- Build script = only for preparing new data

---

If you plan to extend this project (real-time feeds, backend, etc.), the current structure is a solid foundation.

