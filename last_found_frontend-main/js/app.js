/* ═══════════════════════════════════════════════════════════
   Lost & Found Portal — Shared JavaScript
   ═══════════════════════════════════════════════════════════ */

const API_BASE = 'http://127.0.0.1:8000/api';

// ──── Token Management ────
function getToken() {
    return localStorage.getItem('lf_token');
}

function setToken(token) {
    localStorage.setItem('lf_token', token);
}

function removeToken() {
    localStorage.removeItem('lf_token');
    localStorage.removeItem('lf_user');
}

function getUser() {
    const u = localStorage.getItem('lf_user');
    return u ? JSON.parse(u) : null;
}

function setUser(user) {
    localStorage.setItem('lf_user', JSON.stringify(user));
}

function isLoggedIn() {
    return !!getToken();
}

function logout() {
    removeToken();
    window.location.href = 'index.html';
}

// ──── Auth-guarded fetch wrapper ────
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};

    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    const token = getToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    options.headers = headers;

    const response = await fetch(url, options);

    if (response.status === 401) {
        removeToken();
        window.location.href = 'login.html';
        return null;
    }

    return response;
}

// ──── Toast Notifications ────
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ──── Navbar Rendering ────
function renderNavbar(activePage = '') {
    const user = getUser();
    const loggedIn = isLoggedIn();

    const nav = document.getElementById('main-navbar');
    if (!nav) return;

    let linksHTML = '';
    if (loggedIn) {
        const adminLink = user && user.role === 'admin'
            ? `<a href="admin.html" class="${activePage === 'admin' ? 'active' : ''}" style="color: var(--warning);">Admin</a>`
            : '';
        linksHTML = `
            <a href="dashboard.html" class="${activePage === 'dashboard' ? 'active' : ''}">Browse</a>
            <a href="report.html" class="${activePage === 'report' ? 'active' : ''}">Report Item</a>
            <a href="my-items.html" class="${activePage === 'my-items' ? 'active' : ''}">My Items</a>
            ${adminLink}
            <span style="color: var(--accent); font-weight: 500; padding: 8px 12px; font-size: 0.85rem;">
                ${user ? user.full_name : 'User'}
            </span>
            <a href="#" onclick="logout(); return false;" style="color: var(--danger);">Logout</a>
        `;
    } else {
        linksHTML = `
            <a href="login.html" class="${activePage === 'login' ? 'active' : ''}">Login</a>
            <a href="register.html" class="btn-primary btn-sm" style="color:#000;">Sign Up</a>
        `;
    }

    nav.innerHTML = `
        <div class="nav-container">
            <a href="${loggedIn ? 'dashboard.html' : 'index.html'}" class="nav-logo">
                <img src="assets/logo.png" alt="Lost & Found">
                <span>Lost <span style="color: var(--accent);">&</span> Found</span>
            </a>
            <div class="nav-links">
                ${linksHTML}
            </div>
        </div>
    `;
}

// ──── Format Date ────
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
        return dateStr;
    }
}

// ──── Category Badge ────
function categoryBadge(category) {
    const cls = category === 'LOST' ? 'badge-lost' : 'badge-found';
    return `<span class="badge ${cls}">${category}</span>`;
}

// ──── Status Badge ────
function statusBadge(status) {
    const map = {
        'OPEN': 'badge-open',
        'CLAIMED': 'badge-claimed',
        'CLOSED': 'badge-found',
    };
    return `<span class="badge ${map[status] || 'badge-open'}">${status}</span>`;
}

// ──── Image to Base64 ────
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

// ──── Fetch current user profile ────
async function fetchCurrentUser() {
    if (!isLoggedIn()) return null;
    try {
        const resp = await apiFetch('/me');
        if (resp && resp.ok) {
            const user = await resp.json();
            setUser(user);
            return user;
        }
    } catch (e) {
        console.error('Failed to fetch user:', e);
    }
    return null;
}

// ──── Page init helper ────
function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

function requireAdmin() {
    if (!requireAuth()) return false;
    const user = getUser();
    if (!user || user.role !== 'admin') {
        window.location.href = 'dashboard.html';
        return false;
    }
    return true;
}
