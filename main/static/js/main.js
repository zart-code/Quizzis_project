// Автоматическое скрытие flash сообщений
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideOut 0.3s';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Анимация для slideOut
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Подтверждение удаления
function confirmDelete(message) {
    return confirm(message || 'Вы уверены, что хотите удалить?');
}

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Навигационное меню для мобильных устройств
const navToggle = document.createElement('button');
navToggle.className = 'nav-toggle';
navToggle.innerHTML = '☰';
navToggle.style.cssText = `
    display: none;
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.5rem;
`;

if (window.innerWidth <= 768) {
    const navMenu = document.querySelector('.nav-menu');
    const navbar = document.querySelector('.navbar .container');
    
    if (navMenu && navbar) {
        navbar.insertBefore(navToggle, navMenu);
        navToggle.style.display = 'block';
        
        navToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
        });
        
        // Добавляем стили для активного меню
        const mobileStyle = document.createElement('style');
        mobileStyle.textContent = `
            @media (max-width: 768px) {
                .nav-menu {
                    position: absolute;
                    top: 100%;
                    left: 0;
                    right: 0;
                    background: white;
                    flex-direction: column;
                    padding: 1rem;
                    box-shadow: 0 5px 10px rgba(0,0,0,0.1);
                    display: none;
                }
                
                .nav-menu.active {
                    display: flex;
                }
            }
        `;
        document.head.appendChild(mobileStyle);
    }
}

// Анимация для элементов при скролле
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.animation = 'fadeInUp 0.6s ease-out';
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Анимация fadeInUp
const animStyle = document.createElement('style');
animStyle.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(animStyle);

// Применяем наблюдатель к карточкам
document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.quiz-card, .feature-card, .stat-card');
    cards.forEach(card => observer.observe(card));
});

// Валидация форм
const forms = document.querySelectorAll('form');
forms.forEach(form => {
    form.addEventListener('submit', function(e) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.style.borderColor = 'var(--danger)';
                
                setTimeout(() => {
                    field.style.borderColor = '';
                }, 3000);
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            alert('Пожалуйста, заполните все обязательные поля');
        }
    });
});

// Предпросмотр цвета квиза
const colorInput = document.getElementById('color');
if (colorInput) {
    colorInput.addEventListener('input', function() {
        // Можно добавить предпросмотр выбранного цвета
        const preview = document.querySelector('.color-preview');
        if (preview) {
            preview.style.background = this.value;
        }
    });
}

// Таймер для квиза
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Уведомления
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.innerHTML = `
        ${message}
        <button class="close-alert" onclick="this.parentElement.remove()">×</button>
    `;
    
    let container = document.querySelector('.flash-messages');
    if (!container) {
        container = document.createElement('div');
        container.className = 'flash-messages';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}



// Функция для установки сортировки
function setSort(sortType) {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('sort', sortType);

    // Сохраняем поисковый запрос если есть
    const searchInput = document.getElementById('searchInput');
    if (searchInput && searchInput.value) {
        currentUrl.searchParams.set('search', searchInput.value);
    }

    window.location.href = currentUrl.toString();
}

// Быстрый поиск при нажатии Enter
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const form = document.getElementById('searchForm');
                if (form) {
                    form.submit();
                }
            }
        });
    }
});

// Автоматическая отправка формы при изменении поиска (опционально)
// Раскомментируйте если хотите live search
/*
document.addEventListener('DOMContentLoaded', function() {
    let searchTimeout;
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (this.value.length >= 3 || this.value.length === 0) {
                    const form = document.getElementById('searchForm');
                    if (form) {
                        form.submit();
                    }
                }
            }, 500);
        });
    }
});
*/

// ============================================
// СТРАНИЦА СОЗДАНИЯ КВИЗА
// ============================================

// Выбор предустановленного цвета
document.addEventListener('DOMContentLoaded', function() {
    const colorPresets = document.querySelectorAll('.color-preset');
    if (colorPresets.length > 0) {
        colorPresets.forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const colorInput = document.getElementById('color');
                if (colorInput) {
                    colorInput.value = this.dataset.color;
                }
            });
        });
    }
});

// Конвертация минут в секунды при отправке формы создания квиза
document.addEventListener('DOMContentLoaded', function() {
    const createQuizForm = document.getElementById('createQuizForm') || document.getElementById('quiz-form');
    if (createQuizForm) {
        createQuizForm.addEventListener('submit', function(e) {
            const timeLimitInput = document.getElementById('time_limit');
            if (timeLimitInput) {
                const minutes = parseInt(timeLimitInput.value) || 0;
                timeLimitInput.value = minutes * 60;
            }
        });
    }
});

// Подсветка выбранной темы
document.addEventListener('DOMContentLoaded', function() {
    const themeRadios = document.querySelectorAll('.theme-radio');
    if (themeRadios.length > 0) {
        themeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                console.log('Выбрана тема:', this.value);
                // Можно добавить дополнительные действия при выборе темы
            });
        });
    }
});

// Валидация формы создания квиза
document.addEventListener('DOMContentLoaded', function() {
    const createQuizForm = document.getElementById('createQuizForm') || document.getElementById('quiz-form');
    if (createQuizForm) {
        createQuizForm.addEventListener('submit', function(e) {
            const themeRadios = document.querySelectorAll('.theme-radio');
            const themeSelected = document.querySelector('.theme-radio:checked');

            if (themeRadios.length > 0 && !themeSelected) {
                e.preventDefault();
                alert('Пожалуйста, выберите тему квиза');
                return false;
            }

            const titleInput = document.getElementById('title') || document.getElementById('quiz-title');
            if (titleInput) {
                const title = titleInput.value.trim();
                if (!title) {
                    e.preventDefault();
                    alert('Пожалуйста, введите название квиза');
                    return false;
                }
            }
        });
    }
});

let count = 0;
const labels = ['A', 'B', 'C', 'D'];
const times = [15, 20, 30, 45, 60];

function makeTimeOpts(i) {
    return times.map(
        (timeValue) => `
            <input type="radio"
                   class="time-opt"
                   name="q${i}_time"
                   value="${timeValue}"
                   id="qt${i}_${timeValue}"
                   ${timeValue === 30 ? 'checked' : ''}>
            <label for="qt${i}_${timeValue}">${timeValue} сек</label>
        `,
    ).join('');
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

function collectAnswerState(i) {
    const state = {
        texts: [],
        checked: [],
        numberValue: '',
    };

    for (let j = 0; j < 4; j += 1) {
        const textInput = document.querySelector(`input[name="q${i}_ans${j}"]`);
        if (textInput) {
            state.texts[j] = textInput.value;
        }
    }

    const checkedInputs = document.querySelectorAll(`input[name="q${i}_correct"]:checked`);
    state.checked = Array.from(checkedInputs).map((input) => input.value);

    const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
    if (numberInput) {
        state.numberValue = numberInput.value;
    }

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
        if (input) {
            input.checked = true;
        }
    });

    const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
    if (numberInput && state.numberValue !== undefined) {
        numberInput.value = state.numberValue;
    }
}

function makeQuestion(i) {
    const questionsContainer = document.getElementById('questions-container');
    if (!questionsContainer) {
        return;
    }

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
            <input type="text"
                   class="q-input"
                   name="q${i}_text"
                   placeholder="Введите текст вопроса..."
                   required>
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

function setQuestionData(i, questionData) {
    const typeSelect = document.getElementById(`q${i}_type`);
    const questionInput = document.querySelector(`input[name="q${i}_text"]`);
    const coefficientInput = document.querySelector(`input[name="q${i}_coefficient"]`);

    if (typeSelect && questionData.type) {
        typeSelect.value = questionData.type;
        updateAnswers(i);
    }

    if (questionInput) {
        questionInput.value = questionData.text || '';
    }
    if (coefficientInput) {
        coefficientInput.value = questionData.coefficient || 1;
    }

    if (questionData.type === 'single' || questionData.type === 'multiple') {
        const answers = Array.isArray(questionData.answers) ? questionData.answers : [];
        answers.forEach((answer, index) => {
            const answerInput = document.querySelector(`input[name="q${i}_ans${index}"]`);
            const correctInput = document.querySelector(`input[name="q${i}_correct"][value="${index}"]`);

            if (answerInput) {
                answerInput.value = answer.text || '';
            }
            if (correctInput && answer.is_correct) {
                correctInput.checked = true;
            }
        });
    } else if (questionData.type === 'number') {
        const numberInput = document.querySelector(`input[name="q${i}_correct_number"]`);
        if (
            numberInput
            && questionData.correct_number !== null
            && questionData.correct_number !== undefined
        ) {
            numberInput.value = questionData.correct_number;
        }
    }

    if (questionData.time) {
        const timeInput = document.querySelector(
            `input[name="q${i}_time"][value="${questionData.time}"]`,
        );
        if (timeInput) {
            timeInput.checked = true;
        }
    }
}

function initQuizForm() {
    const initialData = window.quizFormInitialData;

    if (
        initialData
        && Array.isArray(initialData.questions)
        && initialData.questions.length > 0
    ) {
        initialData.questions.forEach((questionData) => {
            count += 1;
            makeQuestion(count);
            setQuestionData(count, questionData);
        });
        return;
    }

    count += 1;
    makeQuestion(count);
}

function renumberQuestions() {
    const blocks = document.querySelectorAll('#questions-container .q-block');

    blocks.forEach((block, index) => {
        const i = index + 1;

        block.id = `qblock${i}`;

        const title = block.querySelector('.q-block-title');
        if (title) {
            title.textContent = `Вопрос ${i}`;
        }

        const removeBtn = block.querySelector('.q-remove-btn');
        if (removeBtn) {
            removeBtn.setAttribute('onclick', `removeQuestion(${i})`);
        }

        const typeSelect = block.querySelector('.q-select');
        if (typeSelect) {
            typeSelect.name = `q${i}_type`;
            typeSelect.id = `q${i}_type`;
            typeSelect.setAttribute('onchange', `updateAnswers(${i})`);
        }

        const questionInput = block.querySelector('.q-row input.q-input[name$="_text"]');
        if (questionInput) {
            questionInput.name = `q${i}_text`;
        }

        const coefficientInput = block.querySelector('.q-row input.q-input[name$="_coefficient"]');
        if (coefficientInput) {
            coefficientInput.name = `q${i}_coefficient`;
        }

        const answersContainer = block.querySelector('[id$="_answers"]');
        if (answersContainer) {
            answersContainer.id = `q${i}_answers`;

            const answerRows = answersContainer.querySelectorAll('.answer-row');
            answerRows.forEach((row, j) => {
                const correctInput = row.querySelector('input[type="radio"], input[type="checkbox"]');
                if (correctInput) {
                    correctInput.name = `q${i}_correct`;
                    correctInput.id = `q${i}c${j}`;
                }

                const answerTextInput = row.querySelector('input.q-input');
                if (answerTextInput) {
                    answerTextInput.name = `q${i}_ans${j}`;
                }
            });

            const numberInput = answersContainer.querySelector('input[name$="_correct_number"]');
            if (numberInput) {
                numberInput.name = `q${i}_correct_number`;
            }
        }

        const timeInputs = block.querySelectorAll('.time-opt');
        const timeLabels = block.querySelectorAll('.time-opts label');

        timeInputs.forEach((input, labelIndex) => {
            input.name = `q${i}_time`;
            input.id = `qt${i}_${input.value}`;

            if (timeLabels[labelIndex]) {
                timeLabels[labelIndex].setAttribute('for', input.id);
            }
        });
    });

    count = blocks.length;
}

function removeQuestion(i) {
    const element = document.getElementById(`qblock${i}`);
    if (element) {
        element.remove();
        renumberQuestions();
    }
}

function updateAnswers(i) {
    const type = document.getElementById(`q${i}_type`).value;
    const answersContainer = document.getElementById(`q${i}_answers`);
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

const addQuestionBtn = document.getElementById('add-question-btn');
if (addQuestionBtn) {
    addQuestionBtn.addEventListener('click', () => {
        count += 1;
        makeQuestion(count);
    });

    initQuizForm();
}


// Lobby polling is declared in lobby.html, where Django can render the URL.
const lobbyApiUrlFromStatic = null;
function copyLink(){navigator.clipboard.writeText(document.getElementById('join-link').textContent)}
function fetchPlayers(){
    // Проверяем, находимся ли мы на странице создания квиза
    if (window.location.pathname.includes('/quiz/create/')) {
        window.isCreateQuizPage = true;
    }
    if (!lobbyApiUrlFromStatic || window.isCreateQuizPage) return;
    fetch(lobbyApiUrlFromStatic).then(r=>r.json()).then(data=>{
        document.getElementById('player-count').textContent=data.count;
        const list=document.getElementById('players-list');
        list.innerHTML=data.players.length===0?'<li class="players-empty">Ожидание игроков...</li>':data.players.map(p=>`<li class="player-chip">👤 ${p.username}</li>`).join('');
        document.getElementById('start-btn').disabled=data.count===0;
        document.getElementById('lock-status-badge').innerHTML=data.is_locked?'<span class="lbadge lbadge-danger">Закрыто</span>':'<span class="lbadge lbadge-success">Открыто</span>';
    });
}

document.addEventListener('DOMContentLoaded', function () {
    const toggles = document.querySelectorAll('.js-info-toggle');
    const backdrop = document.getElementById('quizInfoBackdrop');
    const modalBody = document.getElementById('quizInfoModalBody');
    const closeBtn = document.getElementById('quizInfoCloseBtn');

    if (!toggles.length || !backdrop || !modalBody) {
        return;
    }

    function closeModal() {
        backdrop.classList.remove('is-open');
        document.body.style.overflow = '';
    }

    toggles.forEach(function (toggle) {
        toggle.addEventListener('click', function (event) {
            event.preventDefault();
            const popupId = toggle.dataset.quizId;
            const template = document.getElementById(popupId);

            if (!template) {
                return;
            }

            modalBody.innerHTML = template.innerHTML;
            backdrop.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        });
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    document.addEventListener('click', function (event) {
        if (event.target === backdrop) {
            closeModal();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeModal();
        }
    });
});


// Экспортируем функции для использования в других файлах
window.confirmDelete = confirmDelete;
window.showNotification = showNotification;
window.formatTime = formatTime;
