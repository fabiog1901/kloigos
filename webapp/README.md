# 👋 Welcome to the Κλοηγός (Kloigos) Web App!

This directory is home to the web user interface for the **Κλοηγός API server**. We’ve kept things intentionally simple and "dependency-light."

Our goal? A UI that is easy to read, easy to debug, and easy for both humans and AI to understand. 🧠✨

## 🌟 Why you’ll love this design:

* **Zero Build Steps:** No bundlers, no compilers, no waiting. 🚀
* **FastAPI Friendly:** Served directly as a static file.
* **LLM-Ready:** The code structure is clean enough for AI to reason about easily.
* **Pure Power:** High readability and low mental overhead.

---

## 🏗️ High-Level Architecture

The app is a **Single-Page Application (SPA)** contained within a single HTML file. No complex routing or hidden project structures here!

**The Flow:**

1. **Browser** loads `index.html` (Structure + Style + Logic).
2. **JavaScript** handles the state and behavior.
3. **FastAPI** receives HTTP calls via `/api` endpoints.

---

## 🛠️ The Tech Stack

We’ve chosen a "Back to Basics" approach to keep things fast and maintainable:

* **HTML5:** Standard, semantic markup. 🏷️
* **CSS:** Plain CSS kept close to the markup for easy reading. 🎨
* **JavaScript:** Vanilla JS using modern browser APIs. 🍦
* **Alpine.js:** Our secret sauce for reactivity! We use it for state management (`x-data`), event handling (`@click`), and simple loops (`x-for`) without the bulk of React or Vue.

---

## 📱 Application Structure

The app toggles between two main "modes" using a simple tab system:

1. **Dashboard View 🖥️**

    * Manage compute units (allocate, deallocate, initialize).
    * **API Inspector:** See live HTTP requests and responses as they happen!

2. **Playbooks View 📜**

* Browse and edit available playbooks.
* Save changes directly back to the backend.

---

## 🧠 JavaScript & State Design

Everything happens inside a single `<script>` tag using a central Alpine component: `x-data="app()"`.

* **Explicit State:** UI flags, loading icons, and data are all in one place.
* **Clean API:** Helper functions handle fetch calls and base64 encoding.
* **No Magic:** State changes are driven by user actions, making debugging a breeze. 🐛🚫
