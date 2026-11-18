# Format string / инъекция в шаблон форматирования

Отдельно от SSTI: здесь **сам шаблон** (не данные) управляется пользователем.
Python `.format`, C `printf`, PHP `sprintf`, Java `String.format`.

## Признаки

```python
# Python: пользователь задаёт шаблон
msg = request.args["msg"].format(name=user.name)
msg = "{0.__class__}".format(user_input)          # доступ к атрибутам
template = Template(user_input); template.substitute(...)  # OK, но см. ниже
```

```c
printf(user_buf);                 // C: format string vulnerability
syslog(LOG_ERR, user_buf);
```

```php
echo sprintf($_GET["fmt"], $value);       // PHP: аргументы/утечки
```

```java
String.format(userInput, secret);         // Java: чтение аргументов
```

## PoC

```bash
# Python .format: доступ к атрибутам/индексам
curl -s 'http://SVC/greet?msg={0.__class__.__mro__[1].__subclasses__}'
# Python: DoS на ширине поля
curl -s 'http://SVC/greet?msg={:>99999999}'
# C: утечка стека и запись
./svc '%p %p %p %p %p %p'
./svc '%n'
# PHP/Java: чтение лишних аргументов
curl -s 'http://SVC/fmt?f=%s%s%s%s'
```

## Фикс

Python — никогда не форматируй шаблон из ввода:

```python
# ПЛОХО
return request.args["msg"].format(name=user.name)

# ХОРОШО: данные подставляются в фиксированный шаблон
return "Hello, {name}".format(name=user.name)
# или f-строка (шаблон в коде, данные в значениях)
return f"Hello, {user.name}"
```

Если реально нужен пользовательский шаблон — только `string.Template` с
безопасным `$name` (без доступа к атрибутам) и подстановкой из whitelist:

```python
from string import Template
t = Template(request.args["msg"])
return t.safe_substitute({k: v for k, v in allowed.items()})
```

C — всегда явный формат:

```c
printf("%s", user_buf);           // не printf(user_buf)
fputs(user_buf, stdout);
```

PHP/Java — формат константой, аргументы данными:

```php
echo htmlspecialchars($_GET["msg"]);       // без sprintf от ввода
```

```java
String.format("Hello, %s", userInput);
```

Бинарники в A/D (если исходников нет):
- Firegex/regex-фильтр на вход: `%[0-9$]*n`, длинные цепочки `%[0-9$]*[xsp]`
  (это временная мера).
- Патч: заменить вызов `printf(buf)` на `printf("%s", buf)` (бинарь/патч-хук,
  LD_PRELOAD только если контролируешь запуск).

## Не сломать чекер

- Чекер обычно шлёт обычный текст — фикс «шаблон в коде» его не трогает.
- Не бань символ `%`/`{` глобально: в легитимных данных они бывают.
- Если сервис по контракту принимает шаблоны — сузь до безопасных плейсхолдеров
  (`$name`), но проверь, что чекер не использует `%s`/`{}`.

## Проверка

```bash
curl -si 'http://SVC/greet?msg={0.__class__}'    # литерал в ответе, не объект
./svc '%p %p %n'                                  # без утечек/креша
# чекер-симулятор + watch_status 1-2 тика
```

## Обходы, которые проверить

- Python: `{0[0]}`, `{0.__dict__}`, `{0.__getitem__(0)}`, вложенные `{}` в
  f-string, `%`-форматирование со словарём (`%(x)s`).
- Доступ к атрибутам через `string.Formatter.get_field` — если используешь
  собственный Formatter, запрети `get_field`/`get_value` (переопредели).
- C: `%n`, `%hn`, `%hhn`, позиционные `%7$n`, wide-форматы `%lc`/`%ls`.
- PHP: `%n` нет, но `%1$s` читает переданные аргументы; SQL-подобные данные
  внутри строки формата.
- Java: `%t`/`%d` с неверным типом → исключение (DoS), `%1$tm` и т.п.
