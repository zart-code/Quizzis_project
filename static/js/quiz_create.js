// ============================================
// Страница создания / редактирования квиза
// ============================================
import {
    QUIZ_LABELS as labels,
    TIME_OPTIONS as times,
    DEFAULT_TIME,
    DOM_IDS,
} from './constants.js';

import {
    quizCreateState,
    nextQuestionIndex,
    resetQuestionIndex,
} from './quiz_create_state.js';

// ---------- Строители разметки ----------

function makeTimeOpts(i) {
    return times.map((timeValue) => `
        <input type="radio"
               class="time-opt"
               name="q${i}_time"
               value="${timeValue}"
               id="qt${i}_${timeValue}"
               ${timeValue === DEFAULT_TIME ? 'checked' : ''}>
        <label for="qt${i}_${timeValue}">${timeValue} сек</label>
    `).join('');
}

function makeAnswersSingle(i) {
    return `<div class="answers-grid">${labels.map(
        (label, index) => `
            <div class="answer-row">
                <input type="radio" name="q${i}_correct" value="${index}" id="q${i}c${index}">
                <span class="ans-label">${label}</span>
                <input type="text"
                       class="q-input"
                       name="q${i}_ans${index}"
                       placeholder="Вариант ${label}"
                       required>
            </div>
        `,
    ).join('')}</div>`;
}

function makeAnswersMultiple(i) {
    return `<div class="answers-grid">${labels.map(
        (label, index) => `
            <div class="answer-row">
                <input type="checkbox" name="q${i}_correct" value="${index}" id="q${i}c${index}">
                <span class="ans-label">${label}</span>
                <input type="text"
                       class="q-input"
                       name="q${i}_ans${index}"
                       placeholder="Вариант ${label}"
                       required>
            </div>
        `,
    ).join('')}</div>`;
}

function makeAnswersNumber(i) {
    return `
        <div class="q-row">
            <label>Правильное число</label>
            <input type="number"
                   step="any"
                   class="q-input"
                   name="q${i}_correct_number"
                   placeholder="Введите число..."
                   required>
        </div>
    `;
}

function makeAnswersText() {
    return '<p class="text-hint">💬 Ответ проверяется преподавателем вручную</p>';
}

// ---------- Состояние ответов ----------

function collectAnswerState(i) {
    const state = { texts: [], checked: [], numberValue: '' };

    for (let j = 0; j < 4; j += 1) {
        const textInput = document.querySelector(`input[name="q${i}_ans${j}"]`);
        if (textInput) state.texts[j] = textInput.value;
    }

    const checkedInputs = document.querySelectorAll(`input[name="q${i}_correct"]:checked`);
    state.checked = Array.from(checkedInputs).map((input) => input.value);

    const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
    if (numberInput) state.numberValue = numberInput.value;

    return state;
}

function restoreAnswerState(i, state) {
    for (let j = 0; j < 4; j += 1) {
        const textInput = document.querySelector(`input[name="q${i}_ans${j}"]`);
        if (textInput && state.texts[j] !== undefined) {
            textInput.value = state.texts[j];
        }
    }

    state.checked.forEach((value) => {
        const input = document.querySelector(`input[name="q${i}_correct"][value="${value}"]`);
        if (input) input.checked = true;
    });

    const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
    if (numberInput && state.numberValue !== undefined) {
        numberInput.value = state.numberValue;
    }
}

// ---------- Создание блока вопроса ----------

function autoGrow(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 'px';
}

function makeQuestion(i) {
    const questionsContainer = document.getElementById(DOM_IDS.QUESTIONS_CONTAINER);
    if (!questionsContainer) return;

    const html = `<div class="q-block" id="qblock${i}">
        <div class="q-block-header">
            <span class="q-block-title">Вопрос ${i}</span>
            <button type="button" class="q-remove-btn" onclick="removeQuestion(${i})">✕ Удалить</button>
        </div>
        <div class="q-row">
            <label>Тип вопроса</label>
            <select class="q-select" name="q${i}_type" id="q${i}_type" onchange="updateAnswers(${i})">
                <option value="single">Одиночный выбор</option>
                <option value="multiple">Множественный выбор</option>
                <option value="text">Текстовый</option>
                <option value="number">Числовой</option>
            </select>
        </div>
        <div class="q-row">
            <label>Текст вопроса</label>
            <textarea class="q-input q-textarea"
                      name="q${i}_text"
                      rows="2"
                      placeholder="Введите текст вопроса..."
                      oninput="autoGrow(this)"
                      required></textarea>
        </div>
        <div class="q-row">
            <label>Коэффициент</label>
            <input type="number"
                   class="q-input"
                   name="q${i}_coefficient"
                   min="1"
                   step="1"
                   value="1"
                   required>
        </div>
        <div id="q${i}_answers">${makeAnswersSingle(i)}</div>
        <div class="q-row" style="margin-top:1rem">
            <label>⏱ Время на ответ</label>
            <div class="time-opts">${makeTimeOpts(i)}</div>
        </div>
    </div>`;

    questionsContainer.insertAdjacentHTML('beforeend', html);
}

// ---------- Заполнение данными ----------

function setQuestionData(i, questionData) {
    // 1. Тип
    const typeSelect = document.getElementById(`q${i}_type`);
    if (typeSelect && questionData.type) {
        typeSelect.value = questionData.type;
        updateAnswers(i);
    }

    // 2. Текст вопроса (textarea)
    const questionInput = document.querySelector(`[name="q${i}_text"]`);
    if (questionInput) {
        questionInput.value = questionData.text || '';
        autoGrow(questionInput);
    }

    // 3. Коэффициент
    const coefficientInput = document.querySelector(`input[name="q${i}_coefficient"]`);
    if (coefficientInput) {
        coefficientInput.value = questionData.coefficient || 1;
    }

    // 4. Ответы
    if (questionData.type === 'single' || questionData.type === 'multiple') {
        const answers = Array.isArray(questionData.answers) ? questionData.answers : [];
        answers.forEach((answer, index) => {
            const answerInput = document.querySelector(`input[name="q${i}_ans${index}"]`);
            const correctInput = document.querySelector(`input[name="q${i}_correct"][value="${index}"]`);

            if (answerInput) answerInput.value = answer.text || '';
            if (correctInput && answer.is_correct) correctInput.checked = true;
        });
    } else if (questionData.type === 'number') {
        const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
        if (numberInput && questionData.correct_number != null) {
            numberInput.value = questionData.correct_number;
        }
    }

    // 5. Время
    if (questionData.time) {
        const timeInput = document.querySelector(
            `input[name="q${i}_time"][value="${questionData.time}"]`,
        );
        if (timeInput) timeInput.checked = true;
    }
}

// ---------- Инициализация формы ----------

function initQuizForm() {
    const initialData = window.quizFormInitialData;

    if (initialData && Array.isArray(initialData.questions) && initialData.questions.length > 0) {
        initialData.questions.forEach((questionData) => {
            const i = nextQuestionIndex();
            makeQuestion(i);
            setQuestionData(i, questionData);
        });
        return;
    }

    const i = nextQuestionIndex();
    makeQuestion(i);
}

function renumberQuestions() {
    const blocks = document.querySelectorAll('#questions-container .q-block');

    blocks.forEach((block, index) => {
        const i = index + 1;

        block.id = `qblock${i}`;

        const title = block.querySelector('.q-block-title');
        if (title) title.textContent = `Вопрос ${i}`;

        const removeBtn = block.querySelector('.q-remove-btn');
        if (removeBtn) removeBtn.setAttribute('onclick', `removeQuestion(${i})`);

        const typeSelect = block.querySelector('.q-select');
        if (typeSelect) {
            typeSelect.name = `q${i}_type`;
            typeSelect.id = `q${i}_type`;
            typeSelect.setAttribute('onchange', `updateAnswers(${i})`);
        }

        // textarea — селектор без input
        const questionInput = block.querySelector('[name$="_text"]');
        if (questionInput) questionInput.name = `q${i}_text`;

        const coefficientInput = block.querySelector('input.q-input[name$="_coefficient"]');
        if (coefficientInput) coefficientInput.name = `q${i}_coefficient`;

        const answersContainer = block.querySelector('[id$="_answers"]');
        if (answersContainer) {
            answersContainer.id = `q${i}_answers`;

            answersContainer.querySelectorAll('.answer-row').forEach((row, j) => {
                const correctInput = row.querySelector('input[type="radio"], input[type="checkbox"]');
                if (correctInput) {
                    correctInput.name = `q${i}_correct`;
                    correctInput.id = `q${i}c${j}`;
                }

                const answerTextInput = row.querySelector('input.q-input');
                if (answerTextInput) answerTextInput.name = `q${i}_ans${j}`;
            });

            const numberInput = answersContainer.querySelector('input[name$="_correct_number"]');
            if (numberInput) numberInput.name = `q${i}_correct_number`;
        }

        const timeInputs = block.querySelectorAll('.time-opt');
        const timeLabels = block.querySelectorAll('.time-opts label');

        timeInputs.forEach((input, labelIndex) => {
            input.name = `q${i}_time`;
            input.id = `qt${i}_${input.value}`;
            if (timeLabels[labelIndex]) timeLabels[labelIndex].setAttribute('for', input.id);
        });
    });

    resetQuestionIndex(blocks.length);
}

function removeQuestion(i) {
    const element = document.getElementById(`qblock${i}`);
    if (element) {
        element.remove();
        renumberQuestions();
    }
}

function updateAnswers(i) {
    const typeSelect = document.getElementById(`q${i}_type`);
    const answersContainer = document.getElementById(`q${i}_answers`);
    if (!typeSelect || !answersContainer) return;

    const type = typeSelect.value;
    const state = collectAnswerState(i);

    if (type === 'single') {
        answersContainer.innerHTML = makeAnswersSingle(i);
    } else if (type === 'multiple') {
        answersContainer.innerHTML = makeAnswersMultiple(i);
    } else if (type === 'number') {
        answersContainer.innerHTML = makeAnswersNumber(i);
    } else {
        answersContainer.innerHTML = makeAnswersText();
    }

    restoreAnswerState(i, state);
}

// ---------- Импорт из JSON ----------

function mapJsonType(jsonType) {
    switch (jsonType) {
        case 'single_choice': return 'single';
        case 'multiple_choice': return 'multiple';
        case 'number': return 'number';
        case 'text': return 'text';
        default: return jsonType;
    }
}

function findClosestTime(value) {
    let closest = times[0];
    let minDiff = Math.abs(value - times[0]);
    for (let i = 1; i < times.length; i++) {
        const diff = Math.abs(value - times[i]);
        if (diff < minDiff) {
            minDiff = diff;
            closest = times[i];
        }
    }
    return closest;
}

function populateFormFromJson(data) {
    const titleInput = document.getElementById(DOM_IDS.QUIZ_TITLE);
    if (titleInput && data.title) titleInput.value = data.title;

    const container = document.getElementById(DOM_IDS.QUESTIONS_CONTAINER);
    if (!container) return;
    container.innerHTML = '';
    resetQuestionIndex(0);

    if (!Array.isArray(data.questions) || data.questions.length === 0) {
        window.showNotification?.('В файле нет вопросов', 'error');
        return;
    }

    data.questions.forEach((q) => {
        const i = nextQuestionIndex();
        makeQuestion(i);

        const type = mapJsonType(q.type);

        const typeSelect = document.getElementById(`q${i}_type`);
        if (typeSelect) {
            typeSelect.value = type;
            updateAnswers(i);
        }

        const textInput = document.querySelector(`[name="q${i}_text"]`);
        if (textInput && q.text) {
            textInput.value = q.text;
            autoGrow(textInput);
        }

        const coeffInput = document.querySelector(`input[name="q${i}_coefficient"]`);
        if (coeffInput && q.coefficient !== undefined) coeffInput.value = q.coefficient;

        if ((type === 'single' || type === 'multiple') && Array.isArray(q.options)) {
            q.options.forEach((opt, idx) => {
                const ansInput = document.querySelector(`input[name="q${i}_ans${idx}"]`);
                if (ansInput && opt.text) ansInput.value = opt.text;

                if (opt.isCorrect) {
                    const correctInput = document.querySelector(
                        `input[name="q${i}_correct"][value="${idx}"]`,
                    );
                    if (correctInput) correctInput.checked = true;
                }
            });
        }

        if (type === 'number' && q.correctAnswer !== undefined) {
            const numInput = document.querySelector(`input[name="q${i}_correct_number"]`);
            if (numInput) numInput.value = q.correctAnswer;
        }

        if (q.timeLimit) {
            const timeValue = findClosestTime(q.timeLimit);
            const timeInput = document.querySelector(
                `input[name="q${i}_time"][value="${timeValue}"]`,
            );
            if (timeInput) timeInput.checked = true;
        }
    });

    window.showNotification?.('Квиз загружен из JSON. Проверьте данные и нажмите «Сохранить».', 'success');
}

function initJsonDropzone() {
    const dropzone = document.getElementById('json-dropzone');
    const fileInput = document.getElementById('json-file-input');
    const dropContent = document.getElementById('json-drop-content');
    if (!dropzone || !fileInput) return;

    // Глобально глушим дефолт, чтобы файл не открывался при промахе
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleJsonFile(e.target.files[0]);
    });

    dropzone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('cq-import-dropzone--active');
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('cq-import-dropzone--active');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dropzone.contains(e.relatedTarget)) {
            dropzone.classList.remove('cq-import-dropzone--active');
        }
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('cq-import-dropzone--active');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleJsonFile(files[0]);
    });

    function handleJsonFile(file) {
        if (!file.name.endsWith('.json')) {
            window.showNotification?.('Пожалуйста, выберите файл формата .json', 'error');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                populateFormFromJson(data);
                if (dropContent) {
                    dropContent.innerHTML =
                        '<span class="cq-import-mini-icon">✅</span>' +
                        '<div class="cq-import-mini-text"><strong>Загружено</strong>' +
                        '<span>' + window.escapeHtml(file.name) + '</span></div>';
                }
            } catch (err) {
                window.showNotification?.('Ошибка чтения JSON: ' + err.message, 'error');
            }
        };
        reader.readAsText(file);
    }
}

// ---------- Инициализация страницы ----------

document.addEventListener('DOMContentLoaded', () => {
    // 1. Данные для режима редактирования (из json_script в шаблоне)
    const dataEl = document.getElementById('quiz-initial-data');
    if (dataEl) {
        try {
            window.quizFormInitialData = JSON.parse(dataEl.textContent);
        } catch (err) {
            console.error('Не удалось распарсить quiz-initial-data', err);
        }
    }

    // 2. AI-кнопка (URL передаётся через data-url в шаблоне)
    const aiBtn = document.getElementById('ai-generate-btn');
    if (aiBtn && aiBtn.dataset.url) {
        aiBtn.style.cursor = 'pointer';
        aiBtn.addEventListener('click', () => {
            window.location.href = aiBtn.dataset.url;
        });
    }

    // 3. Импорт из JSON
    initJsonDropzone();

    // 4. Основная форма
    const addQuestionBtn = document.getElementById(DOM_IDS.ADD_QUESTION_BTN);
    if (addQuestionBtn) {
        addQuestionBtn.addEventListener('click', () => {
            makeQuestion(nextQuestionIndex());
        });
        initQuizForm();
    }
});

// ---------- Экспорт для inline-обработчиков и main.js ----------

window.makeQuestion = makeQuestion;
window.removeQuestion = removeQuestion;
window.updateAnswers = updateAnswers;
window.autoGrow = autoGrow;