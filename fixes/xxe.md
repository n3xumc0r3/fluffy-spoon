# XXE — фикс

## Признаки

```bash
grep -rnE 'etree\.parse|lxml\.parse|minidom|xml\.dom|simplexml_load|DOMDocument|DocumentBuilder|SAXParser|libxml' .
```

Симптом: `<!DOCTYPE ... SYSTEM "file:///etc/passwd">` / `http://` в XML,
ответ содержит файлы или приходит запрос на внутренний хост.

## Фикс

### Python: defusedxml (лучший вариант)

```python
# pip install defusedxml
from defusedxml import ElementTree as ET
root = ET.fromstring(user_xml)
```

### Python: stdlib

```python
import xml.etree.ElementTree as ET
# В CPython ElementTree не раскрывает внешние сущности по умолчанию,
# но lxml/minidom - да. Для lxml:
from lxml import etree
parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
root = etree.fromstring(user_xml, parser=parser)
```

### PHP

```php
libxml_set_external_entity_loader(function () { return null; });
$dom = new DOMDocument();
$dom->loadXML($xml, LIBXML_NONET);
// или simplexml_load_string($xml, 'SimpleXMLElement', LIBXML_NONET)
```

### Java

```java
DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
dbf.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
dbf.setFeature("http://xml.org/sax/features/external-general-entities", false);
dbf.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
dbf.setXIncludeAware(false);
dbf.setExpandEntityReferences(false);
```

### Node

```js
// libxmljs: { noent: false } и не включай dtdload
// fast-xml-parser по умолчанию не раскрывает сущности — проверь версию/опции
```

## Не сломать чекер

- Легитимный XML чекера обычно без DOCTYPE — запрет doctype безопасен.
- Если сервис по заданию принимает XML с DTD/схемой (SOAP), запрет doctype
  сломает чекер: тогда оставь DTD, но выключи external entities и сеть.

## Проверка

```bash
cat > evil.xml <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>
EOF
curl --data @evil.xml -H 'Content-Type: application/xml' http://localhost:8080/parse
```
