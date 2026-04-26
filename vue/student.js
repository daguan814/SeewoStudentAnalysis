const apiBase = ["127.0.0.1", "localhost"].includes(window.location.hostname) ? "http://127.0.0.1:8000" : "";

const studentTitle = document.getElementById("studentTitle");
const studentSubtitle = document.getElementById("studentSubtitle");
const studentClass = document.getElementById("studentClass");
const studentSex = document.getElementById("studentSex");
const studentTeacher = document.getElementById("studentTeacher");
const studentMessage = document.getElementById("studentMessage");
const metricList = document.getElementById("metricList");
const backToItem = document.getElementById("backToItem");
const commentaryButton = document.getElementById("commentaryButton");
const commentaryMessage = document.getElementById("commentaryMessage");
const commentaryText = document.getElementById("commentaryText");
const aiDoctorPanel = document.getElementById("aiDoctorPanel");
const aiDoctorText = document.getElementById("aiDoctorText");
const parentNoteText = document.getElementById("parentNoteText");
const parentNoteSave = document.getElementById("parentNoteSave");
const parentNoteClear = document.getElementById("parentNoteClear");
const parentNoteMessage = document.getElementById("parentNoteMessage");
const metricMaxScore = 20;
let commentaryTypingTimer = null;
let commentaryUtterance = null;

function setMessage(text, type = "") {
  studentMessage.textContent = text;
  studentMessage.className = `message ${type}`.trim();
}

function setCommentaryMessage(text, type = "") {
  commentaryMessage.textContent = text;
  commentaryMessage.className = `message ${type}`.trim();
}

function setParentNoteMessage(text, type = "") {
  parentNoteMessage.textContent = text;
  parentNoteMessage.className = `message parent-note-message ${type}`.trim();
}

function stopDoctorPlayback() {
  if (commentaryTypingTimer) {
    window.clearInterval(commentaryTypingTimer);
    commentaryTypingTimer = null;
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  commentaryUtterance = null;
}

function speakCommentary(text) {
  if (!window.speechSynthesis || !text) {
    return;
  }

  commentaryUtterance = new SpeechSynthesisUtterance(text);
  commentaryUtterance.lang = "zh-CN";
  commentaryUtterance.rate = 0.95;
  commentaryUtterance.pitch = 1.06;
  commentaryUtterance.volume = 1;
  window.speechSynthesis.speak(commentaryUtterance);
}

function playDoctorCommentary(text) {
  stopDoctorPlayback();
  aiDoctorPanel.classList.add("visible", "speaking");
  aiDoctorText.textContent = "";

  const fullText = (text || "").trim();
  if (!fullText) {
    aiDoctorText.textContent = "这次点评还没有生成内容。";
    aiDoctorPanel.classList.remove("speaking");
    return;
  }

  let index = 0;
  commentaryTypingTimer = window.setInterval(() => {
    index += 1;
    aiDoctorText.textContent = fullText.slice(0, index);
    if (index >= fullText.length) {
      window.clearInterval(commentaryTypingTimer);
      commentaryTypingTimer = null;
      aiDoctorPanel.classList.remove("speaking");
    }
  }, 70);

  speakCommentary(fullText);
}

async function fetchJson(path) {
  const response = await fetch(`${apiBase}${path}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function postJson(path, payload = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
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
  parentNoteSave.dataset.itemId = itemId;
  parentNoteSave.dataset.studentId = studentId;
  parentNoteClear.dataset.itemId = itemId;
  parentNoteClear.dataset.studentId = studentId;

  try {
    const data = await fetchJson(`/api/items/${itemId}/students/${studentId}`);
    studentTitle.textContent = `${data.student_name || `学生${data.student_number}`} · 学生画像`;
    studentSubtitle.textContent = `${data.item_name} · 座位序号 ${data.student_number}`;
    studentClass.textContent = data.class_name || "-";
    studentSex.textContent = data.sex || "-";
    studentTeacher.textContent = data.teacher || "-";
    renderMetrics(data.metrics || []);
    setMessage("学生画像加载完成。", "success");
    loadParentNote(data.parent_message || "", data.student_name || `学生${data.student_number}`);
  } catch (error) {
    setMessage(error.message, "error");
    metricList.innerHTML = '<div class="heatmap-empty">学生画像加载失败。</div>';
    setParentNoteMessage("学生信息加载失败，暂时无法绑定家长赠语。", "error");
  }
}

function loadParentNote(savedText, studentName) {
  parentNoteText.value = savedText;
  if (savedText) {
    setParentNoteMessage(`已载入 ${studentName} 的家长赠语。`, "success");
  } else {
    setParentNoteMessage("还没有保存赠语，可以先写一句鼓励孩子的话。");
  }
}

async function saveParentNote() {
  const itemId = parentNoteSave.dataset.itemId;
  const studentId = parentNoteSave.dataset.studentId;
  if (!itemId || !studentId) {
    setParentNoteMessage("缺少学生参数，无法保存赠语。", "error");
    return;
  }

  const content = parentNoteText.value.trim();
  parentNoteSave.disabled = true;
  parentNoteClear.disabled = true;
  setParentNoteMessage("正在保存家长赠语...");
  try {
    await postJson(`/api/items/${itemId}/students/${studentId}/parent-message`, {
      parent_message: content,
    });
    setParentNoteMessage(content ? "家长赠语已保存到数据库。" : "内容为空，已保存为空白赠语。", "success");
  } catch (error) {
    setParentNoteMessage(error.message, "error");
  } finally {
    parentNoteSave.disabled = false;
    parentNoteClear.disabled = false;
  }
}

async function clearParentNote() {
  const itemId = parentNoteClear.dataset.itemId;
  const studentId = parentNoteClear.dataset.studentId;
  if (!itemId || !studentId) {
    setParentNoteMessage("缺少学生参数，无法清空赠语。", "error");
    return;
  }

  parentNoteText.value = "";
  parentNoteSave.disabled = true;
  parentNoteClear.disabled = true;
  setParentNoteMessage("正在清空家长赠语...");
  try {
    await postJson(`/api/items/${itemId}/students/${studentId}/parent-message`, {
      parent_message: "",
    });
    setParentNoteMessage("家长赠语已清空。", "success");
  } catch (error) {
    setParentNoteMessage(error.message, "error");
  } finally {
    parentNoteSave.disabled = false;
    parentNoteClear.disabled = false;
  }
}

parentNoteSave.addEventListener("click", saveParentNote);
parentNoteClear.addEventListener("click", clearParentNote);
parentNoteText.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveParentNote();
  }
});

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
    playDoctorCommentary(data.commentary || "");
  } catch (error) {
    setCommentaryMessage(error.message, "error");
    stopDoctorPlayback();
    aiDoctorPanel.classList.add("visible");
    aiDoctorPanel.classList.remove("speaking");
    aiDoctorText.textContent = error.message || "AI 点评生成失败，请稍后重试。";
  } finally {
    commentaryButton.disabled = false;
    commentaryButton.textContent = "生成点评";
  }
});

loadStudentProfile();
