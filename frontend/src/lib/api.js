const TOKEN_KEY = 'missionledger_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

function withQuery(path, params) {
  if (!params) return path
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') q.set(key, value)
  }
  const qs = q.toString()
  return qs ? `${path}?${qs}` : path
}

async function request(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      /* response had no JSON body */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  signup: (payload) => request('/auth/signup', { method: 'POST', body: payload }),
  getSecurityQuestions: () => request('/auth/security-questions'),
  loginStep1: (payload) => request('/auth/login', { method: 'POST', body: payload }),
  loginStep2: (payload) => request('/auth/login/verify-security', { method: 'POST', body: payload }),
  me: () => request('/auth/me'),

  setupMessage: (message, history) => request('/setup/message', { method: 'POST', body: { message, history } }),
  setupCreate: (plan) => request('/setup/create', { method: 'POST', body: plan }),

  getInvitePreview: (token) => request(`/invite/${token}`),
  acceptInvite: (token) => request(`/invite/${token}/accept`, { method: 'POST' }),

  listWorkspaces: () => request('/workspaces'),
  createWorkspace: (payload) => request('/workspaces', { method: 'POST', body: payload }),
  getWorkspace: (id) => request(`/workspaces/${id}`),

  listMembers: (workspaceId) => request(`/workspaces/${workspaceId}/members`),
  addMember: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/members`, { method: 'POST', body: payload }),
  removeMember: (workspaceId, membershipId) =>
    request(`/workspaces/${workspaceId}/members/${membershipId}`, { method: 'DELETE' }),
  updateMemberRole: (workspaceId, membershipId, role) =>
    request(`/workspaces/${workspaceId}/members/${membershipId}/role`, { method: 'PUT', body: { role } }),

  listPots: (workspaceId) => request(`/workspaces/${workspaceId}/pots`),
  createPot: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/pots`, { method: 'POST', body: payload }),
  updatePotApproval: (workspaceId, potId, payload) =>
    request(`/workspaces/${workspaceId}/pots/${potId}/approval`, { method: 'PUT', body: payload }),

  listTransactions: (workspaceId, filters) =>
    request(withQuery(`/workspaces/${workspaceId}/transactions`, filters)),
  createTransaction: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/transactions`, { method: 'POST', body: payload }),
  updateTransaction: (workspaceId, transactionId, payload) =>
    request(`/workspaces/${workspaceId}/transactions/${transactionId}`, { method: 'PUT', body: payload }),
  deleteTransaction: (workspaceId, transactionId) =>
    request(`/workspaces/${workspaceId}/transactions/${transactionId}`, { method: 'DELETE' }),
  decideTransaction: (workspaceId, transactionId, approve, reason) =>
    request(`/workspaces/${workspaceId}/transactions/${transactionId}/decision`, {
      method: 'POST',
      body: { approve, reason },
    }),

  listApprovals: (workspaceId) => request(`/workspaces/${workspaceId}/approvals`),
  countMyApprovals: (workspaceId) => request(`/workspaces/${workspaceId}/approvals/count`),
  bulkDecide: (workspaceId, transactionIds, approve, reason) =>
    request(`/workspaces/${workspaceId}/approvals/bulk`, {
      method: 'POST',
      body: { transaction_ids: transactionIds, approve, reason },
    }),

  getSettleUp: (workspaceId) => request(`/workspaces/${workspaceId}/settle-up`),

  setCoupleStatus: (workspaceId, isCouple) =>
    request(`/workspaces/${workspaceId}/couple`, { method: 'PUT', body: { is_couple: isCouple } }),
  setTaxPackEnabled: (workspaceId, enabled) =>
    request(`/workspaces/${workspaceId}/tax-pack`, { method: 'PUT', body: { enabled } }),
  setIncome: (workspaceId, membershipId, monthlyIncome) =>
    request(`/workspaces/${workspaceId}/members/${membershipId}/income`, {
      method: 'PUT',
      body: { monthly_income: monthlyIncome },
    }),

  listAIUsage: (workspaceId) => request(`/workspaces/${workspaceId}/ai-usage`),

  getAttention: (workspaceId) => request(`/workspaces/${workspaceId}/attention`),

  sendChatMessage: (workspaceId, message) =>
    request(`/workspaces/${workspaceId}/chat`, { method: 'POST', body: { message } }),

  listFeedback: () => request('/feedback'),
  getFeedbackSummary: () => request('/feedback/summary'),
  submitFeedback: (payload) => request('/feedback', { method: 'POST', body: payload }),

  listSettlements: (workspaceId) => request(`/workspaces/${workspaceId}/settle-up/payments`),
  recordPayment: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/settle-up/payments`, { method: 'POST', body: payload }),

  listRecurring: (workspaceId) => request(`/workspaces/${workspaceId}/recurring`),
  createRecurring: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/recurring`, { method: 'POST', body: payload }),
  deleteRecurring: (workspaceId, chargeId) =>
    request(`/workspaces/${workspaceId}/recurring/${chargeId}`, { method: 'DELETE' }),

  listAuditLog: (workspaceId) => request(`/workspaces/${workspaceId}/audit-log`),
  listSecurityLog: (workspaceId) => request(`/workspaces/${workspaceId}/security-log`),

  getCostsSummary: () => request('/costs/summary'),
  getCostsDaily: (days) => request(withQuery('/costs/daily', { days })),
  getCostsRaw: () => request('/costs/raw'),

  listFeatureFlags: () => request('/feature-flags'),
  setFeatureFlag: (name, enabled) =>
    request(`/feature-flags/${name}`, { method: 'PUT', body: { enabled } }),

  async uploadStatement(workspaceId, file) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/workspaces/${workspaceId}/intake/statement`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    return res.json()
  },
  async uploadIntakeReceipt(workspaceId, file) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/workspaces/${workspaceId}/intake/receipt`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    return res.json()
  },
  async uploadGrantPdf(workspaceId, file) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/workspaces/${workspaceId}/intake/grant`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    return res.json()
  },
  confirmIntakeTransactions: (workspaceId, rows) =>
    request(`/workspaces/${workspaceId}/intake/confirm-transactions`, { method: 'POST', body: { rows } }),
  confirmIntakeGrant: (workspaceId, payload) =>
    request(`/workspaces/${workspaceId}/intake/confirm-grant`, { method: 'POST', body: payload }),

  async generateReport(workspaceId) {
    const res = await fetch(`/api/workspaces/${workspaceId}/reports/generate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="(.+)"/)
    return { blob, filename: match ? match[1] : 'report.pdf' }
  },

  getTaxPack: (workspaceId, year) => request(withQuery(`/workspaces/${workspaceId}/tax-pack`, { year })),

  async generateTaxPackPdf(workspaceId, year) {
    const res = await fetch(withQuery(`/api/workspaces/${workspaceId}/tax-pack/pdf`, { year }), {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="(.+)"/)
    return { blob, filename: match ? match[1] : 'tax_prep_pack.pdf' }
  },

  async getTaxPackCsv(workspaceId, year) {
    const res = await fetch(withQuery(`/api/workspaces/${workspaceId}/tax-pack/csv`, { year }), {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText)
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="(.+)"/)
    return { blob, filename: match ? match[1] : 'tax_prep_pack.csv' }
  },

  async uploadReceipt(workspaceId, transactionId, file) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/workspaces/${workspaceId}/transactions/${transactionId}/receipt`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || res.statusText)
    }
    return res.json()
  },

  async getReceiptObjectUrl(workspaceId, transactionId) {
    const res = await fetch(`/api/workspaces/${workspaceId}/transactions/${transactionId}/receipt`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) throw new Error('Could not load receipt')
    const blob = await res.blob()
    return { url: URL.createObjectURL(blob), isPdf: blob.type === 'application/pdf' }
  },
}
