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
    const createQuizForm = document.getElementById('createQuizForm');
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
    const createQuizForm = document.getElementById('createQuizForm');
    if (createQuizForm) {
        createQuizForm.addEventListener('submit', function(e) {
            const themeSelected = document.querySelector('.theme-radio:checked');

            if (!themeSelected) {
                e.preventDefault();
                alert('Пожалуйста, выберите тему квиза');
                return false;
            }

            const titleInput = document.getElementById('title');
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

// Экспортируем функции для использования в других файлах
window.confirmDelete = confirmDelete;
window.showNotification = showNotification;
window.formatTime = formatTime;
