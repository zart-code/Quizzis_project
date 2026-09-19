// ============================================
// Общий JS: используется на всех страницах
// ============================================

// ---------- XSS-защита ----------
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

// ---------- Подтверждение удаления ----------
function confirmDelete(message) {
    return confirm(message || 'Вы уверены, что хотите удалить?');
}
window.confirmDelete = confirmDelete;

// ---------- Форматирование времени ----------
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}
window.formatTime = formatTime;

// ---------- Уведомления ----------
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
window.showNotification = showNotification;

// ---------- Keyframes, используемые в JS ----------
(function injectKeyframes() {
    const st = document.createElement('style');
    st.textContent = `
        @keyframes slideOut {
            to { transform: translateX(100%); opacity: 0; }
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to   { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(st);
})();

// ---------- Авто-скрытие flash-сообщений ----------
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.animation = 'slideOut 0.3s';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// ---------- Мобильное меню ----------
(function initMobileNav() {
    if (window.innerWidth > 768) return;

    const navMenu = document.querySelector('.nav-menu');
    const navbar = document.querySelector('.navbar .container');
    if (!navMenu || !navbar) return;

    const navToggle = document.createElement('button');
    navToggle.className = 'nav-toggle';
    navToggle.innerHTML = '☰';
    navToggle.style.cssText = `
        display: block;
        background: none;
        border: none;
        font-size: 1.5rem;
        color: var(--text-primary);
        cursor: pointer;
        padding: 0.5rem;
    `;

    navbar.insertBefore(navToggle, navMenu);

    navToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
    });

    const mobileStyle = document.createElement('style');
    mobileStyle.textContent = `
        @media (max-width: 768px) {
            .nav-menu {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: #1A1A2E;
                flex-direction: column;
                padding: 1rem;
                box-shadow: 0 5px 10px rgba(0,0,0,0.3);
                display: none;
            }
            .nav-menu.active { display: flex; }
        }
    `;
    document.head.appendChild(mobileStyle);
})();

// ---------- Smooth scroll по якорям ----------
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (href === '#') return;
        const target = document.querySelector(href);
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// ---------- Анимация появления карточек ----------
(function initScrollAnimations() {
    const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'fadeInUp 0.6s ease-out';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.quiz-card, .feature-card, .stat-card, .mq-card')
            .forEach(card => observer.observe(card));
    });
})();

// ---------- Базовая валидация форм ----------
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function (e) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.style.borderColor = 'var(--danger)';
                setTimeout(() => { field.style.borderColor = ''; }, 3000);
            }
        });

        if (!isValid) {
            e.preventDefault();
            showNotification('Пожалуйста, заполните все обязательные поля', 'error');
        }
    });
});

// ---------- Сортировка (страница списка квизов) ----------
// TODO: переедет в pages/quizzes_list.js, когда разложим страницы
function setSort(sortType) {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('sort', sortType);
    const searchInput = document.getElementById('searchInput');
    if (searchInput && searchInput.value) {
        currentUrl.searchParams.set('search', searchInput.value);
    }
    window.location.href = currentUrl.toString();
}
window.setSort = setSort;