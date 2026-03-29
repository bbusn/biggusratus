function formatDuration(seconds) {
  if (seconds < 60) return Math.floor(seconds) + "s";
  if (seconds < 3600)
    return Math.floor(seconds / 60) + "m " + Math.floor(seconds % 60) + "s";
  return (
    Math.floor(seconds / 3600) + "h " + Math.floor((seconds % 3600) / 60) + "m"
  );
}

function getOsDisplay(os) {
  const display = {
    linux: "Linux",
    windows: "Windows",
    darwin: "macOS",
    unknown: "Unknown",
  };
  return display[os] || display.unknown;
}

function getOsBadgeClass(os) {
  const classes = {
    linux: "bg-green-100 text-green-700",
    windows: "bg-blue-100 text-blue-700",
    darwin: "bg-amber-100 text-amber-700",
    unknown: "bg-gray-100 text-gray-600",
  };
  return classes[os] || classes.unknown;
}

function setLoading(loading) {
  const skeletonBody = document.getElementById("skeleton-body");
  const agentsBody = document.getElementById("agents-body");
  if (loading) {
    skeletonBody.classList.remove("hidden");
    agentsBody.classList.add("hidden");
  } else {
    skeletonBody.classList.add("hidden");
    agentsBody.classList.remove("hidden");
  }
}

function loadAgents() {
  setLoading(true);
  fetch("/api/agents")
    .then((r) => r.json())
    .then((data) => {
      const tbody = document.getElementById("agents-body");
      if (data.agents.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="7" class="px-4 py-12 text-center text-gray-400">No agents connected</td></tr>';
        setLoading(false);
        return;
      }
      tbody.innerHTML = data.agents
        .map(
          (a) => `
                <tr class="hover:bg-gray-50 transition-colors">
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            <span class="text-gray-700">Online</span>
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <span class="font-mono text-sm text-gray-800 break-all whitespace-normal">${
                              a.id
                            }</span>
                            <button onclick="navigator.clipboard.writeText('${
                              a.id
                            }')" class="text-gray-400 hover:text-gray-600 cursor-pointer" title="Copy ID">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                                </svg>
                            </button>
                        </div>
                    </td>
                    <td class="px-4 py-3 font-mono text-sm text-gray-800">${
                      a.ip
                    }</td>
                    <td class="px-4 py-3">
                        <span class="inline-block px-2 py-1 rounded text-xs font-medium ${getOsBadgeClass(
                          a.os
                        )}">${getOsDisplay(a.os)}</span>
                    </td>
                    <td class="px-4 py-3 text-gray-600">${formatDuration(
                      a.uptime
                    )}</td>
                    <td class="px-4 py-3 text-gray-600">${formatDuration(
                      a.idle
                    )} ago</td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-1">
                            <button onclick="testAgent('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Test">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                            </button>
                            <button onclick="showDownloadModal('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Download">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                                </svg>
                            </button>
                            <button onclick="showUploadModal('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Upload">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                                </svg>
                            </button>
                            <button onclick="disconnectAgent('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors cursor-pointer" title="Disconnect">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                    </td>
                </tr>
            `
        )
        .join("");
      setLoading(false);
    })
    .catch(() => setLoading(false));
}

loadAgents();
setInterval(loadAgents, 5000);

function testAgent(agentId) {
  if (!confirm(`Send test command to agent ${agentId.substring(0, 8)}...?`))
    return;
  fetch(`/api/agents/${agentId}/test`, { method: "POST" })
    .then((r) => r.json())
    .then((data) => alert(data.success ? "Test OK" : `Error: ${data.error}`))
    .catch(() => alert("Request failed"));
}

function disconnectAgent(agentId) {
  if (!confirm(`Disconnect agent ${agentId.substring(0, 8)}...?`)) return;
  fetch(`/api/agents/${agentId}/disconnect`, { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      alert(data.success ? "Disconnected" : `Error: ${data.error}`);
      loadAgents();
    })
    .catch(() => alert("Request failed"));
}

function showDownloadModal(agentId) {
  const remote = prompt("Remote file path:");
  if (!remote) return;
  const local = prompt("Local save path:");
  if (!local) return;
  fetch(`/api/agents/${agentId}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remote_path: remote, local_path: local }),
  })
    .then((r) => r.json())
    .then((data) => alert(data.success ? "Downloaded" : `Error: ${data.error}`))
    .catch(() => alert("Request failed"));
}

function showUploadModal(agentId) {
  const local = prompt("Local file path:");
  if (!local) return;
  const remote = prompt("Remote destination path:");
  if (!remote) return;
  fetch(`/api/agents/${agentId}/upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ local_path: local, remote_path: remote }),
  })
    .then((r) => r.json())
    .then((data) => alert(data.success ? "Uploaded" : `Error: ${data.error}`))
    .catch(() => alert("Request failed"));
}
