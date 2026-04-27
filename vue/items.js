const apiBase = "";

const itemsSummary = document.getElementById("itemsSummary");
const itemsMessage = document.getElementById("itemsMessage");
const itemsBody = document.getElementById("itemsBody");
const heatmapTitle = document.getElementById("heatmapTitle");
const heatmapMessage = document.getElementById("heatmapMessage");
const heatmapContainer = document.getElementById("heatmapContainer");

let itemSortBy = "id";
let itemSortOrder = "desc";
let selectedItemId = null;

function setMessage(element, text, type = "") {
  element.textContent = text;
  element.className = `message ${type}`.trim();
}

function updateSortHeaders(selector, activeField, activeOrder) {
  document.querySelectorAll(selector).forEach((th) => {
    const isActive = th.dataset.sortField === activeField;
    const icon = th.querySelector(".sort-icon");
    th.classList.toggle("active", isActive);
    if (!icon) return;
    icon.textContent = isActive ? (activeOrder === "asc" ? "▲" : "▼") : "↕";
  });
}

async function fetchJson(path) {
  const response = await fetch(`${apiBase}${path}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

function renderHeatmap(item, students) {
  if (!students.length) {
    heatmapContainer.className = "heatmap-empty";
    heatmapContainer.textContent = "该课堂没有学生数据。";
    return;
  }

  const maxRow = Math.max(...students.map((student) => student.row_number));
  const maxCol = Math.max(...students.map((student) => student.column_number));
  const map = new Map();
  students.forEach((student) => {
    map.set(`${student.row_number}-${student.column_number}`, student);
  });

  const rows = [];
  for (let row = 1; row <= maxRow; row += 1) {
    const cells = [];
    for (let col = 1; col <= maxCol; col += 1) {
      const student = map.get(`${row}-${col}`);
      if (!student) {
        cells.push('<div class="seat empty-seat"></div>');
        continue;
      }
      const colorHex = student.color_hex || "#2f6bff";
      const name = student.student_name || `学生${student.student_number}`;
      const detailUrl = `./student.html?item_id=${encodeURIComponent(item.id)}&student_id=${encodeURIComponent(student.id)}`;
      cells.push(
        `<a class="seat seat-link" data-student-url="${detailUrl}" href="${detailUrl}" style="background:${colorHex}" title="点击查看 ${name} 的详情">
          <span class="seat-name">${name}</span>
        </a>`
      );
    }
    rows.push(`<div class="seat-row">${cells.join("")}</div>`);
  }

  heatmapContainer.className = "heatmap-board";
  heatmapContainer.innerHTML = rows.join("");
  heatmapTitle.textContent = `${item.item_name} · 热力图`;
}

function renderItems(data) {
  const items = data.items || [];
  itemsSummary.textContent = `共 ${items.length} 节课`;
  if (!items.length) {
    itemsBody.innerHTML = '<tr><td colspan="7" class="empty">暂无课堂数据。</td></tr>';
    return;
  }

  itemsBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td>${item.id}</td>
          <td><a href="#" class="item-link" data-item-id="${item.id}" data-item-name="${item.item_name}">${item.item_name}</a></td>
          <td>${item.class_name}</td>
          <td>${item.teacher}</td>
          <td>${item.student_num}</td>
          <td>${item.student_score_sum}</td>
          <td>${item.created_at}</td>
        </tr>
      `
    )
    .join("");

  document.querySelectorAll(".item-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      selectedItemId = Number(link.dataset.itemId);
      loadHeatmap();
    });
  });
}

async function loadItems() {
  updateSortHeaders(".table-sort", itemSortBy, itemSortOrder);
  setMessage(itemsMessage, "正在加载课堂列表...");
  try {
    const data = await fetchJson(
      `/api/items?sort_by=${encodeURIComponent(itemSortBy)}&sort_order=${encodeURIComponent(itemSortOrder)}`
    );
    renderItems(data);
    const params = new URLSearchParams(window.location.search);
    const initialItemId = Number(params.get("item_id"));
    if (!selectedItemId && initialItemId && (data.items || []).some((item) => item.id === initialItemId)) {
      selectedItemId = initialItemId;
      loadHeatmap();
    }
    setMessage(itemsMessage, "课堂列表加载完成。", "success");
  } catch (error) {
    setMessage(itemsMessage, error.message, "error");
  }
}

async function loadHeatmap() {
  if (!selectedItemId) return;
  setMessage(heatmapMessage, "正在加载热力图...");
  try {
    const data = await fetchJson(`/api/items/${selectedItemId}?sort_by=student_number&sort_order=asc`);
    renderHeatmap(data, data.students || []);
    setMessage(heatmapMessage, "热力图加载完成。", "success");
  } catch (error) {
    setMessage(heatmapMessage, error.message, "error");
    heatmapContainer.className = "heatmap-empty";
    heatmapContainer.textContent = "热力图加载失败。";
  }
}

document.querySelectorAll(".table-sort").forEach((th) => {
  th.addEventListener("click", () => {
    const field = th.dataset.sortField;
    if (itemSortBy === field) {
      itemSortOrder = itemSortOrder === "asc" ? "desc" : "asc";
    } else {
      itemSortBy = field;
      itemSortOrder = field === "id" || field === "created_at" ? "desc" : "asc";
    }
    loadItems();
  });
});

heatmapContainer.addEventListener("click", (event) => {
  const link = event.target.closest(".seat-link");
  if (!link) return;
  event.preventDefault();
  const url = link.dataset.studentUrl || link.getAttribute("href");
  if (url) {
    window.location.href = url;
  }
});

loadItems();
