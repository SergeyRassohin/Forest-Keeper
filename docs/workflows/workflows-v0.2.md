# Forest Keeper — Workflows v0.2

## WF-01 Observer
1. FK получает данные из разрешённых источников.
2. Выполняет нормализацию, сопоставление и проверки.
3. Незначимые события фиксируются без ручной задачи.
4. Значимые случаи становятся Issue/Conflict.
5. Формируется рекомендация.
6. Случай маршрутизируется нужной роли.
7. Решение фиксируется в Decision Registry и Audit.

Observer не блокирует исходные системы.

## WF-02 Advisor
1. Пользователь видит конфликт/аномалию.
2. FK показывает источники, значения, provenance и основание.
3. FK показывает похожие подтверждённые случаи.
4. Формируется рекомендация.
5. Пользователь принимает решение.
6. Решение сохраняется.

## WF-03 Post-check
1. Данные уже появились в исходной системе.
2. FK получает выгрузку или событие.
3. Выполняется анализ.
4. При проблеме создаётся Human Review.
5. Исправление выполняется человеком или будущим controlled publisher.

## WF-04 Controlled Gateway — будущее
1. Кандидат на изменение поступает в FK.
2. FK возвращает PASS / WARNING / REVIEW.
3. PASS означает только отсутствие основания блокировать.
4. REVIEW требует Human Decision.
5. Критическая публикация возможна только после APPROVED.

## MVP workflow
`1C XML + Excel → adapters → raw storage → normalization → matching → conflict detection → recommendation → human decision → Decision Registry → next similar recommendation`
