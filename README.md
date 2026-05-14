image: python:3.13.3-alpine3.20

before_script:
  - python3 -m venv .venv
  - . .venv/bin/activate
  - pip install -r requirements.txt

stages:
  - style
  - test
  - docs          # новая стадия для документации

pylint:
  stage: style
  script:
    - pylint --fail-under=6 --ignore-paths="docs/*" **/*.py
    - echo "Pylint complete."
  artifacts:
    untracked: false
    when: on_success
    expire_in: 30 days

pycodestyle:
    stage: style
    script:
        - pycodestyle --max-line-length=120 **/*.py
        - echo "Pycodestyle complete."
    artifacts:
        untracked: false
        when: on_failure
        expire_in: 30 days

python:
  stage: test
  script:
    - .venv/bin/python manage.py test
    - echo "tests complete."
  artifacts:
    untracked: false
    when: on_failure
    expire_in: 30 days

# ========== ДОКУМЕНТАЦИЯ SPHINX ==========

build-docs:
  stage: docs
  script:
    # Убедимся, что Sphinx установлен (он должен быть в requirements.txt)
    - sphinx-build --version
    # Сборка HTML (замените пути на свои)
    - sphinx-build -b html docs/source/ docs/build/
  artifacts:
    paths:
      - docs/build/
    expire_in: 30 days
  only:
    - main   # или ваша основная ветка

pages:
  stage: docs
  script:
    # GitLab Pages ожидает файлы в папке public
    - mkdir -p public
    - cp -r docs/build/* public/
  artifacts:
    paths:
      - public/
  only:
    - main