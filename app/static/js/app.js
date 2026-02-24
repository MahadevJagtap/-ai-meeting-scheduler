/* ─── AI Meeting Scheduler – Main JS ───────────────────────── */

const API_BASE = '';   // same origin

/* ── Navigation ──────────────────────────────────────────── */
function navigate(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const targetPage = document.getElementById('page-' + pageId);
  if (targetPage) targetPage.classList.add('active');
  const targetNav = document.querySelector(`[data-page="${pageId}"]`);
  if (targetNav) targetNav.classList.add('active');

  // Lazy-load data per page
  if (pageId === 'dashboard') loadDashboard();
  if (pageId === 'preferences') loadPreferences();
}

/* ── Toast ────────────────────────────────────────────────── */
function showToast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const tc = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  tc.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

/* ── Helpers ──────────────────────────────────────────────── */
function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
}

function fmtDt(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

function fmtScore(score) {
  return Math.round((score || 0) * 100) + '%';
}

/* ── Schedule Meeting ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const schedForm = document.getElementById('schedule-form');
  if (schedForm) schedForm.addEventListener('submit', handleSchedule);

  const prefForm = document.getElementById('pref-form');
  if (prefForm) prefForm.addEventListener('submit', handleAddPref);

  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChat();
      }
    });
    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });
  }

  // Navigation bindings
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });

  // Initial page
  navigate('dashboard');
});

/* ── Dashboard ────────────────────────────────────────────── */
async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    const el = document.getElementById('system-status');
    if (el) {
      el.textContent = data.status === 'healthy' ? '🟢 Online' : '🔴 Offline';
      el.style.color = data.status === 'healthy' ? 'var(--green)' : 'var(--red)';
    }
  } catch {
    const el = document.getElementById('system-status');
    if (el) { el.textContent = '🔴 Offline'; el.style.color = 'var(--red)'; }
  }
}

/* ── Schedule Page ────────────────────────────────────────── */
async function handleSchedule(e) {
  e.preventDefault();
  setLoading('schedule-btn', true);
  const resultBox = document.getElementById('schedule-result');
  resultBox.className = 'result-box';

  const payload = {
    user_id: document.getElementById('s-user-id').value.trim() || 'default_user',
    request_text: document.getElementById('s-request').value.trim(),
    participants: document.getElementById('s-participants').value
      .split(',').map(s => s.trim()).filter(Boolean),
    timezone_offset: new Date().getTimezoneOffset(),
  };

  try {
    const res = await fetch(`${API_BASE}/api/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
      showToast('Meeting scheduled! 🎉', 'success');
      renderScheduleSuccess(resultBox, data);
    } else {
      showToast(data.message || 'Scheduling failed', 'error');
      renderScheduleError(resultBox, data);
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
    resultBox.className = 'result-box error show';
    resultBox.innerHTML = `<div class="result-title">⚠️ Network Error</div><div class="result-body">${err.message}</div>`;
  }
  setLoading('schedule-btn', false);
}

function renderScheduleSuccess(box, data) {
  const m = data.meeting || {};
  const slots = (data.suggested_slots || []).slice(0, 3);
  box.className = 'result-box success show';
  box.innerHTML = `
    <div class="result-title">🎉 ${data.message}</div>
    <div class="detail-grid">
      <div class="detail-item"><div class="detail-label">Title</div><div class="detail-value">${m.summary || '—'}</div></div>
      <div class="detail-item"><div class="detail-label">Start</div><div class="detail-value">${fmtDt(m.start)}</div></div>
      <div class="detail-item"><div class="detail-label">End</div><div class="detail-value">${fmtDt(m.end)}</div></div>
      <div class="detail-item"><div class="detail-label">Participants</div><div class="detail-value">${m.participants?.join(', ') || '—'}</div></div>
    </div>
    ${m.calendar_link ? `<a href="${m.calendar_link}" target="_blank" class="btn btn-secondary btn-sm" style="margin-top:14px;display:inline-flex">📅 View in Calendar</a>` : ''}
    ${slots.length ? `
      <div style="margin-top:16px;">
        <div class="detail-label" style="margin-bottom:8px;">Suggested Alternative Slots</div>
        <div class="slots-list">
          ${slots.map(s => `<div class="slot-item"><span class="slot-time">🕐 ${fmtDt(s.start)} – ${fmtDt(s.end)}</span><span class="slot-score">Score: ${fmtScore(s.score)}</span></div>`).join('')}
        </div>
      </div>` : ''}
  `;
}

function renderScheduleError(box, data) {
  box.className = 'result-box error show';
  box.innerHTML = `
    <div class="result-title">❌ Scheduling Failed</div>
    <div class="result-body">${data.message}</div>
    ${(data.suggested_slots || []).length ? `
      <div style="margin-top:14px;">
        <div class="detail-label" style="margin-bottom:8px;">Available Slots</div>
        <div class="slots-list">
          ${data.suggested_slots.slice(0, 3).map(s => `<div class="slot-item"><span class="slot-time">🕐 ${fmtDt(s.start)} – ${fmtDt(s.end)}</span><span class="slot-score">Score: ${fmtScore(s.score)}</span></div>`).join('')}
        </div>
      </div>` : ''}
  `;
}

/* ── Preferences Page ─────────────────────────────────────── */
let currentUserId = 'default_user';

async function loadPreferences() {
  const uid = document.getElementById('pref-user-id')?.value || currentUserId;
  currentUserId = uid;
  const list = document.getElementById('pref-list');
  if (!list) return;
  list.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Loading…</div>';
  try {
    const res = await fetch(`${API_BASE}/api/preferences/${encodeURIComponent(uid)}`);
    const prefs = await res.json();
    renderPreferences(list, prefs);
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div>Could not load preferences</div>';
  }
}

async function filterPreferences() {
  const uid = document.getElementById('pref-user-id')?.value.trim();
  if (uid) { currentUserId = uid; }
  loadPreferences();
}

function renderPreferences(container, prefs) {
  if (!prefs || prefs.length === 0) {
    container.innerHTML = `<div class="empty-state"><div class="icon">💭</div>No preferences found for this user</div>`;
    return;
  }
  container.innerHTML = prefs.map(p => `
    <div class="pref-item" id="pref-${p.id}">
      <span class="pref-text">${p.preference_text}</span>
      <span class="pref-date">${fmtDt(p.created_at)}</span>
      <button class="btn btn-danger btn-sm" onclick="deletePreference(${p.id})">🗑️ Delete</button>
    </div>
  `).join('');
}

async function handleAddPref(e) {
  e.preventDefault();
  setLoading('pref-btn', true);
  const text = document.getElementById('pref-text').value.trim();
  if (!text) { setLoading('pref-btn', false); return; }

  try {
    const res = await fetch(`${API_BASE}/api/preferences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUserId, preference_text: text }),
    });
    if (res.ok) {
      showToast('Preference saved!', 'success');
      document.getElementById('pref-text').value = '';
      loadPreferences();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to save preference', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
  setLoading('pref-btn', false);
}

async function deletePreference(id) {
  try {
    const res = await fetch(`${API_BASE}/api/preferences/${id}`, { method: 'DELETE' });
    if (res.status === 204) {
      document.getElementById(`pref-${id}`)?.remove();
      showToast('Preference deleted', 'info');
    } else {
      showToast('Could not delete preference', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
}

/* ── Chat Page ────────────────────────────────────────────── */
let chatHistory = [];

async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;

  input.value = '';
  input.style.height = 'auto';
  appendChatMessage('user', msg);

  const userId = document.getElementById('chat-user-id')?.value.trim() || 'chat_user';
  appendTypingIndicator();
  setLoading('chat-send-btn', true);

  try {
    // Step 1: Send to /api/chat for intent detection
    const chatRes = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, message: msg, participants: [], timezone_offset: new Date().getTimezoneOffset() }),
    });
    const chatData = await chatRes.json();

    if (chatData.intent === 'general' || chatData.intent === 'calendar') {
      // Display reply directly
      removeTypingIndicator();
      appendChatMessage('ai', chatData.reply);

    } else if (chatData.intent === 'schedule' && chatData.schedule_payload) {
      // Update bubble to show we're working
      removeTypingIndicator();
      appendChatMessage('ai', '📅 Finding the best time and scheduling...');
      appendTypingIndicator();

      // Step 2: Call the actual scheduling API
      const schedRes = await fetch(`${API_BASE}/api/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chatData.schedule_payload),
      });
      const schedData = await schedRes.json();
      removeTypingIndicator();

      if (schedData.success) {
        const m = schedData.meeting || {};
        const slots = (schedData.suggested_slots || []).slice(0, 2);
        let reply = `✅ **Meeting Scheduled!**\n📌 **${m.summary || 'Meeting'}**\n🕐 **Start:** ${fmtDt(m.start)}\n📅 **End:** ${fmtDt(m.end)}`;
        if (m.calendar_link) reply += `\n\n[📅 View in Google Calendar](${m.calendar_link})`;
        if (slots.length) {
          reply += `\n\n**Alternative slots:**\n` + slots.map(s => `• ${fmtDt(s.start)}`).join('\n');
        }
        reply += `\n\n🔔 You'll be notified 10 minutes before via **Email** and **WhatsApp**.`;
        appendChatMessage('ai', reply);
        showToast('Meeting scheduled! 🎉', 'success');
      } else {
        const slots = schedData.suggested_slots || [];
        let reply = `ℹ️ ${schedData.message || 'Scheduling could not be completed.'}`;
        if (slots.length) {
          reply += `\n\n**Available slots:**\n` + slots.slice(0, 3).map(s => `• ${fmtDt(s.start)}`).join('\n');
          reply += `\n\nWould you like me to schedule one of these times?`;
        }
        appendChatMessage('ai', reply);
      }
    }
  } catch (err) {
    removeTypingIndicator();
    appendChatMessage('ai', `⚠️ Something went wrong: ${err.message}`);
  }

  setLoading('chat-send-btn', false);
}

function appendChatMessage(role, text) {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.innerHTML = `
    <div class="chat-avatar">${role === 'ai' ? '🤖' : '👤'}</div>
    <div class="chat-bubble">${text
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="chat-link">$1</a>')
    }</div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function appendTypingIndicator() {
  const msgs = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg ai';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="chat-avatar">🤖</div>
    <div class="chat-bubble" style="padding:14px 18px;">
      <span style="display:flex;gap:5px;align-items:center;">
        <span style="width:7px;height:7px;border-radius:50%;background:var(--text-2);animation:blink 1.2s infinite 0s"></span>
        <span style="width:7px;height:7px;border-radius:50%;background:var(--text-2);animation:blink 1.2s infinite 0.3s"></span>
        <span style="width:7px;height:7px;border-radius:50%;background:var(--text-2);animation:blink 1.2s infinite 0.6s"></span>
      </span>
    </div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function removeTypingIndicator() {
  document.getElementById('typing-indicator')?.remove();
}
