const apiBase = "http://127.0.0.1:8000";

const studentTitle = document.getElementById("studentTitle");
const studentSubtitle = document.getElementById("studentSubtitle");
const studentClass = document.getElementById("studentClass");
const studentSex = document.getElementById("studentSex");
const studentTeacher = document.getElementById("studentTeacher");
const studentScore = document.getElementById("studentScore");
const studentMessage = document.getElementById("studentMessage");
const metricList = document.getElementById("metricList");
const backToItem = document.getElementById("backToItem");
const commentaryButton = document.getElementById("commentaryButton");
const commentaryMessage = document.getElementById("commentaryMessage");
const commentaryText = document.getElementById("commentaryText");
const metricMaxScore = 20;

const colorNameMap = {
  "#2f6bff": "睿智蓝",
  "#35b56a": "探索绿",
  "#f3c64d": "洞察金",
  "#f08a32": "生活橙",
  "#d94b3d": "暖心红",
};

function setMessage(text, type = "") {
  studentMessage.textContent = text;
  studentMessage.className = `message ${type}`.trim();
}

function setCommentaryMessage(text, type = "") {
  commentaryMessage.textContent = text;
  commentaryMessage.className = `message ${type}`.trim();
}

async function fetchJson(path) {
  const response = await fetch(`${apiBase}${path}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function postJson(path) {
  const response = await fetch(`${apiBase}${path}`, { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

function renderMetrics(metrics) {
  const rows = metrics
    .map((metric) => {
      const score = Math.max(0, Math.min(metricMaxScore, Number(metric.score) || 0));
      const width = (score / metricMaxScore) * 100;

      return `
        <div class="metric-row">
          <div class="metric-row-main">
            <div class="metric-row-top">
              <div class="metric-row-label-wrap">
                <span class="metric-dot" style="background:${metric.color_hex}"></span>
                <span class="metric-row-label">${metric.label}</span>
              </div>
              <strong class="metric-row-score" style="color:${metric.color_hex}">${score}/${metricMaxScore}</strong>
            </div>
            <div class="metric-row-bar" aria-label="${metric.label} 得分 ${score}，满分 ${metricMaxScore}">
              <div class="metric-row-fill" style="width:${width}%; background:${metric.color_hex}"></div>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  const explainRows = metrics
    .map(
      (metric) => `
        <div class="metric-explain-row">
          <div class="metric-row-label-wrap">
            <span class="metric-dot" style="background:${metric.color_hex}"></span>
            <span class="metric-row-label">${metric.label}</span>
          </div>
          <p class="metric-explain-text">${metric.description}</p>
        </div>
      `
    )
    .join("");

  metricList.innerHTML = `
    <section class="metric-layout">
      <section class="metric-compact-card">${rows}</section>
      <aside class="metric-explain-card">
        <h3>指标说明</h3>
        <div class="metric-explain-list">${explainRows}</div>
      </aside>
    </section>
  `;
}

async function loadStudentProfile() {
  const params = new URLSearchParams(window.location.search);
  const itemId = params.get("item_id");
  const studentId = params.get("student_id");

  if (!itemId || !studentId) {
    setMessage("缺少学生参数，无法打开详情页。", "error");
    metricList.innerHTML = '<div class="heatmap-empty">没有找到要查看的学生。</div>';
    return;
  }

  backToItem.href = `./index.html?item_id=${encodeURIComponent(itemId)}`;
  setMessage("正在加载学生画像...");
  commentaryButton.dataset.itemId = itemId;
  commentaryButton.dataset.studentId = studentId;

  try {
    const data = await fetchJson(`/api/items/${itemId}/students/${studentId}`);
    studentTitle.textContent = `${data.student_name || `学生${data.student_number}`} · 学生画像`;
    studentSubtitle.textContent = `${data.item_name} · 座位序号 ${data.student_number}`;
    studentClass.textContent = data.class_name || "-";
    studentSex.textContent = data.sex || "-";
    studentTeacher.textContent = data.teacher || "-";
    const colorHex = (data.color_hex || "").toLowerCase();
    const colorName = colorNameMap[colorHex] || "课堂颜色";
    studentScore.innerHTML = `<span class="student-color-chip" style="background:${data.color_hex}"></span>${colorName}`;
    renderMetrics(data.metrics || []);
    setMessage("学生画像加载完成。", "success");
  } catch (error) {
    setMessage(error.message, "error");
    metricList.innerHTML = '<div class="heatmap-empty">学生画像加载失败。</div>';
  }
}

commentaryButton.addEventListener("click", async () => {
  const itemId = commentaryButton.dataset.itemId;
  const studentId = commentaryButton.dataset.studentId;
  if (!itemId || !studentId) {
    setCommentaryMessage("缺少学生参数，无法生成点评。", "error");
    return;
  }

  commentaryButton.disabled = true;
  commentaryButton.textContent = "生成中...";
  setCommentaryMessage("正在请求 DeepSeek 生成点评...");

  try {
    const data = await postJson(`/api/items/${itemId}/students/${studentId}/commentary`);
    commentaryText.textContent = data.commentary || "点评生成成功，但返回内容为空。";
    setCommentaryMessage("AI 点评生成完成。", "success");
  } catch (error) {
    setCommentaryMessage(error.message, "error");
  } finally {
    commentaryButton.disabled = false;
    commentaryButton.textContent = "生成点评";
  }
});

loadStudentProfile();
