(function () {
    "use strict";

    function setupNotificationPanel(toggleId, panelId) {
        var toggle = document.getElementById(toggleId);
        var panel = document.getElementById(panelId);
        if (!toggle || !panel) {
            return;
        }
        toggle.addEventListener("click", function (event) {
            event.stopPropagation();
            panel.classList.toggle("hidden");
        });
        document.addEventListener("click", function () {
            panel.classList.add("hidden");
        });
        panel.addEventListener("click", function (event) {
            event.stopPropagation();
        });
    }

    setupNotificationPanel("notifToggle", "notifPanel");
    setupNotificationPanel("notifToggleM", "notifPanelM");

    (function setupMobileNav() {
        var sidebar = document.getElementById("sidebarNav");
        var navToggle = document.getElementById("navToggle");
        var scrim = document.getElementById("navScrim");
        if (!sidebar || !navToggle) {
            return;
        }
        function closeNav() {
            sidebar.classList.add("-translate-x-full");
            if (scrim) {
                scrim.classList.add("hidden");
            }
        }
        navToggle.addEventListener("click", function (event) {
            event.stopPropagation();
            if (sidebar.classList.contains("-translate-x-full")) {
                sidebar.classList.remove("-translate-x-full");
                if (scrim) {
                    scrim.classList.remove("hidden");
                }
            } else {
                closeNav();
            }
        });
        if (scrim) {
            scrim.addEventListener("click", closeNav);
        }
        sidebar.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", closeNav);
        });
    })();

    (function setupCounters() {
        document.querySelectorAll("[data-counter-target]").forEach(function (field) {
            var target = document.getElementById(field.getAttribute("data-counter-target"));
            if (!target) {
                return;
            }
            function update() {
                target.textContent = String(field.value.length);
            }
            field.addEventListener("input", update);
            update();
        });
    })();

    (function setupConfirmLinks() {
        document.querySelectorAll("form[data-confirm]").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                if (!window.confirm(form.getAttribute("data-confirm"))) {
                    event.preventDefault();
                }
            });
        });
    })();

    (function setupStatsChart() {
        var chart = document.getElementById("stats-chart");
        var body = document.getElementById("stats-chart-body");
        if (!chart || !body) {
            return;
        }

        var colors = {
            FILED: "bg-primary",
            ASSIGNED: "bg-primary",
            IN_PROGRESS: "bg-accent",
            RESOLVED: "bg-accent",
            CLOSED: "bg-success",
            REOPENED: "bg-danger"
        };

        function render(data) {
            body.innerHTML = "";
            var total = data.total || 0;

            var summary = document.createElement("p");
            summary.className = "text-sm text-muted";
            summary.textContent = total + " complaint" + (total === 1 ? "" : "s") + " visible to you.";
            body.appendChild(summary);

            data.by_status.forEach(function (item) {
                var row = document.createElement("div");

                var top = document.createElement("div");
                top.className = "mb-1 flex items-center justify-between text-xs font-semibold";
                var label = document.createElement("span");
                label.className = "text-ink";
                label.textContent = item.label;
                var count = document.createElement("span");
                count.className = "text-muted";
                count.textContent = String(item.count);
                top.appendChild(label);
                top.appendChild(count);

                var track = document.createElement("div");
                track.className = "h-2 w-full rounded-full bg-surface";
                var bar = document.createElement("div");
                bar.className = "h-2 rounded-full " + (colors[item.key] || "bg-primary");
                var pct = total > 0 ? Math.round((item.count / total) * 100) : 0;
                bar.style.width = pct + "%";
                track.appendChild(bar);

                row.appendChild(top);
                row.appendChild(track);
                body.appendChild(row);
            });
        }

        fetch(chart.getAttribute("data-url"), {
            headers: { Accept: "application/json" }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Stats request failed with status " + response.status);
                }
                return response.json();
            })
            .then(render)
            .catch(function (error) {
                console.error(error);
                body.innerHTML = "";
                var message = document.createElement("p");
                message.className = "text-sm text-muted";
                message.textContent = "Could not load the live stats. Refresh to try again.";
                body.appendChild(message);
            });
    })();
})();
