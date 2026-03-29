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
          '<tr><td colspan="6" class="px-4 py-12 text-center text-gray-400">No agents connected</td></tr>';
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
                    <td class="px-4 py-3 font-mono text-sm text-gray-800">${
                      a.id
                    }</td>
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
