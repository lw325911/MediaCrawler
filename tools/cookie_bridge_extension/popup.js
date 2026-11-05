// MediaCrawler Cookie 同步：读取平台域名下的 Cookie，写入 /api/accounts。
// 同一平台 + 备注名再次同步时更新原账号的 Cookie（并重置失败状态）。
const DOMAINS = {
  xhs: ["xiaohongshu.com"],
  dy: ["douyin.com"],
  ks: ["kuaishou.com"],
  bili: ["bilibili.com"],
  wb: ["weibo.com", "weibo.cn"],
  tieba: ["baidu.com"],
  zhihu: ["zhihu.com"],
};

const $ = (id) => document.getElementById(id);

function show(text, ok) {
  $("msg").className = ok ? "ok" : "err";
  $("msg").textContent = text;
}

async function cookieString(platform) {
  const seen = new Map();
  for (const domain of DOMAINS[platform]) {
    for (const c of await chrome.cookies.getAll({ domain })) seen.set(c.name, c.value);
  }
  return [...seen].map(([k, v]) => `${k}=${v}`).join("; ");
}

async function api(server, path, options = {}) {
  const resp = await fetch(server.replace(/\/$/, "") + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
  return body;
}

async function sync() {
  const platform = $("platform").value;
  const name = $("name").value.trim();
  const proxy = $("proxy").value.trim();
  const server = $("server").value.trim();
  await chrome.storage.local.set({ platform, name, proxy, server });

  const cookies = await cookieString(platform);
  if (!cookies) return show("没有读到 Cookie，请先在浏览器里登录该平台", false);

  const { accounts } = await api(server, `/api/accounts?platform=${platform}`);
  const existing = name && accounts.find((a) => a.account_name === name);
  if (existing) {
    await api(server, `/api/accounts/${existing.id}`, {
      method: "PATCH",
      body: JSON.stringify(proxy ? { cookies, proxy, status: "normal" } : { cookies, status: "normal" }),
    });
    show(`已更新账号 ${name}（${existing.id}）`, true);
  } else {
    const acc = await api(server, "/api/accounts", {
      method: "POST",
      body: JSON.stringify({ platform, cookies, account_name: name, proxy }),
    });
    show(`已添加账号 ${acc.id}`, true);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const saved = await chrome.storage.local.get(["platform", "name", "proxy", "server"]);
  for (const key of ["platform", "name", "proxy", "server"]) if (saved[key]) $(key).value = saved[key];
  $("sync").addEventListener("click", () => sync().catch((e) => show(`同步失败：${e.message}`, false)));
});
