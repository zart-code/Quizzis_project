// ============================================
// Состояние страницы создания квиза
// ============================================

// Обёрнуто в объект, потому что импортируемые привязки read-only:
// `import { count }` нельзя мутировать снаружи, а свойство объекта — можно.
export const quizCreateState = {
    count: 0,
};

export function nextQuestionIndex() {
    quizCreateState.count += 1;
    return quizCreateState.count;
}

export function resetQuestionIndex(value = 0) {
    quizCreateState.count = value;
}