// cypress/e2e/translator_critic.cy.js
// UI-tests для приложения "AI Translator & Critic" с использованием Cypress.
// Тесты полностью мокируют сетевые запросы к внешнему API через cy.intercept().

describe('AI Translator & Critic - End-to-End', () => {
  // Перед каждым тестом гарантируем, что приложение доступно по корню '/'
  beforeEach(() => {
    // Если приложение работает на другом порту, измените baseUrl в cypress.config.js
    cy.visit('/');
  });

  it('Успешный перевод и оценка (mocked requests)', () => {
    // Перехватываем все POST-запросы к API и возвращаем разные ответы
    // в зависимости от model_name в теле запроса.
    cy.intercept('POST', 'https://api.mentorpiece.org/v1/process-ai-request', (req) => {
      // req.body содержит JSON-тело запроса. Здесь мы смотрим на поле model_name.
      const model = req.body && req.body.model_name;

      if (model === 'Qwen/Qwen3-VL-30B-A3B-Instruct') {
        // alias для перевода, чтобы затем ждать именно этот вызов
        req.alias = 'translate';
        // Немедленный ответ с нужной структурой
        req.reply({ statusCode: 200, body: { response: 'Mocked Translation: The sun is shining.' } });
        return;
      }

      if (model === 'claude-sonnet-4-5-20250929') {
        // alias для оценки
        req.alias = 'judge';
        req.reply({ statusCode: 200, body: { response: 'Mocked Grade: 9/10. Fluent and accurate.' } });
        return;
      }

      // По умолчанию — возвращаем 500, если модель неизвестна (безопасно выявит ошибку)
      req.reply({ statusCode: 500, body: { response: 'Unknown model' } });
    });

    // Вводим текст в textarea. Используем селекторы по имени полей из шаблона.
    cy.get('textarea[name="original_text"]').clear().type('Солнце светит.');
    // Выбираем язык. В шаблоне опции имеют текст 'English', 'French', 'German'.
    cy.get('select[name="language"]').select('English');

    // Нажимаем кнопку "Перевести" — форма отправится, и сервер выполнит оба запроса
    cy.contains('button', 'Перевести').click();

    // Проверяем, что перевод (Mock 1) был отправлен и получил ответ.
    // cy.wait ожидает, что ранее в обработчике intercept был установлен req.alias = 'translate'.
    cy.wait('@translate').its('request.body').should((body) => {
      // Здесь проверяем, что в запросе действительно присутствует правильная модель
      expect(body).to.have.property('model_name', 'Qwen/Qwen3-VL-30B-A3B-Instruct');
    });

    // Проверяем, что перевод отобразился в UI.
    cy.contains('Mocked Translation: The sun is shining.').should('be.visible');

    // Теперь нажмём кнопку оценки (она также отправляет форму в текущей реализации).
    cy.contains('button', 'Оценить при помощи LLM-as-a-Judge').click();

    // Убедимся, что пришёл запрос на оценку и он использовал нужную модель.
    cy.wait('@judge').its('request.body').should((body) => {
      expect(body).to.have.property('model_name', 'claude-sonnet-4-5-20250929');
    });

    // Проверяем отображение оценки в блоке результатов.
    cy.contains('Mocked Grade: 9/10. Fluent and accurate.').should('be.visible');
  });

  it('Обработка ошибок API: показываем сообщение об ошибке, приложение не падает', () => {
    // Мокаем оба типа запросов, возвращая 500 Internal Server Error
    cy.intercept('POST', 'https://api.mentorpiece.org/v1/process-ai-request', (req) => {
      req.reply({ statusCode: 500, body: { response: 'Server error' } });
    }).as('apiFail');

    // Вводим данные и отправляем форму
    cy.get('textarea[name="original_text"]').clear().type('Солнце светит.');
    cy.get('select[name="language"]').select('English');
    cy.contains('button', 'Перевести').click();

    // Дожидаемся ошибочного запроса
    cy.wait('@apiFail');

    // Проверяем, что в UI появилась строка с сообщением об ошибке.
    // В нашем приложении call_llm возвращает строку, начинающуюся с "Ошибка при обращении к LLM"
    cy.contains('Ошибка при обращении к LLM').should('exist');
  });
});

// Конец файла cypress/e2e/translator_critic.cy.js
