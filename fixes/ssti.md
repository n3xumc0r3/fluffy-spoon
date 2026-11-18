# SSTI (инъекция шаблонов) — фикс

## Признаки

```bash
grep -rnE 'render_template_string|Template\(|from_string|compile\(|twig|Handlebars\.compile|new Function' .
```

Симптом: `{{7*7}}`, `{{config}}`, `${7*7}`, `<%= 7*7 %>` в выводе, отдача
`/etc/passwd` через `{{ ''.__class__... }}`.

## Фикс

### Python / Jinja2

```python
# ПЛОХО
return render_template_string(user_template)

# ХОРОШО 1: не рендерить пользовательский ввод шаблоном
return render_template("page.html", content=user_template)  # экранирование

# ХОРОШО 2: если функциональность "свой шаблон" нужна — sandbox
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
return env.from_string(user_template).render()
```

Sandbox не 100%, но закрывает классику (`__class__`, `__globals__`,
`__subclasses__`). Дополнительно вычищай опасные атрибуты.

### Django

`Template(user_input)` без `Engine` тоже опасен: Django-шаблоны позволяют
вызов методов. Принцип тот же — не рендерь ввод как шаблон.

### PHP Twig

```php
$twig = new \Twig\Environment($loader);
$twig->addExtension(new \Twig\Extension\SandboxExtension($policy));
$twig->enableSandbox();
```

Или просто не пропускай ввод в `Twig->createTemplate($userInput)`.

### Node

```js
// ПЛОХО: Handlebars.compile(req.body.tpl)(ctx)
// ХОРОШО: рендерь только предопределённые шаблоны, ввод - в контекст
```

### Ruby ERB

`ERB.new(user_input).result` — это RCE. Никогда не давай юзеру шаблон.

## Не сломать чекер

- Если сервис по заданию генерирует отчёты по пользовательским шаблонам,
  чекер это использует: sandbox должен сохранить `{{ var }}`, циклы и фильтры.
  Тестируй шаблоны чекера (посмотри в его запросах) до деплоя.
- Не отключай шаблонизацию целиком — сломаешь фичу.

## Проверка

```bash
curl 'http://localhost:8080/render?tpl={{7*7}}'      # 49 -> уязвим
curl 'http://localhost:8080/render?tpl={{config}}'   # должен быть пустой/ошибка
```
