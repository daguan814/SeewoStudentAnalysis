const apiBase = ["127.0.0.1", "localhost"].includes(window.location.hostname) ? "http://127.0.0.1:8000" : "";

const form = document.getElementById("import-form");
const message = document.getElementById("message");
const summary = document.getElementById("summary");
const previewStatus = document.getElementById("previewStatus");
const previewDetail = document.getElementById("previewDetail");
const resultSummary = document.getElementById("resultSummary");
const resultBody = document.getElementById("resultBody");

function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `message ${type}`.trim();
}

function buildFormData(includeMeta = true) {
  const imageInput = document.getElementById("imageFile");
  const file = imageInput.files?.[0];
  if (!file) {
    throw new Error("请先选择一张热力图截图。");
  }

  const formData = new FormData();
  formData.append("image", file);

  if (includeMeta) {
    formData.append("item_name", document.getElementById("itemName").value.trim());
    formData.append("class_name", document.getElementById("className").value.trim());
    formData.append("teacher", document.getElementById("teacher").value.trim());
    formData.append("student_lines_text", document.getElementById("studentLinesText").value);
  }

  return formData;
}

async function request(path, formData) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

function renderPreview(data) {
  summary.textContent = `识别成功，共 ${data.student_count} 个座位`;
  previewStatus.textContent = "识别成功";
  previewDetail.textContent = `识别到 ${data.student_count} 个座位，总分范围 ${data.score_min} - ${data.score_max}。`;
}

function renderImportResult(data) {
  resultSummary.textContent = `入库成功：课堂 ID ${data.item_id}，共 ${data.student_count} 人，总分 ${data.student_score_sum}`;
  resultBody.innerHTML = data.students
    .map(
      (student) => `
        <tr>
          <td>${student.student_number}</td>
          <td>${student.student_name || "-"}</td>
          <td>${student.gender || "-"}</td>
          <td>${student.row_number}</td>
          <td>${student.column_number}</td>
          <td>${student.total_score}</td>
          <td>${student.detail_scores.join(" / ")}</td>
        </tr>
      `
    )
    .join("");
}

document.getElementById("previewButton").addEventListener("click", async () => {
  try {
    setMessage("正在识别图片，请稍等...");
    const data = await request("/api/classroom-image/preview", buildFormData(false));
    renderPreview(data);
    setMessage("识别测试通过，可以继续入库。", "success");
  } catch (error) {
    summary.textContent = "识别测试未通过";
    previewStatus.textContent = "识别失败";
    previewDetail.textContent = "请检查图片是否清晰、完整，并确保主要内容是热力图。";
    setMessage(error.message, "error");
    window.alert(`识别失败：${error.message}`);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    setMessage("正在入库，请稍等...");
    const data = await request("/api/classroom-image/import", buildFormData(true));
    renderImportResult(data);
    setMessage("课堂和学生数据已经写入数据库。", "success");
  } catch (error) {
    setMessage(error.message, "error");
  }
});
