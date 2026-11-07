# M253 · Deco Manager и Location Assets — единый registry snapshot

## Причина

Studio Find получал свежий `/api/location-assets`, но использовал его только в
локальном scan. Видимый Deco Manager продолжал хранить прежние `self.registry`,
template и preview. После Sync `refreshRegistry` обновлял registry, но сбрасывал
выбор на первый asset категории вместо целевого slug.

## Контракт

- Find сохраняет свежий snapshot в Deco Manager.
- Если окно открыто, template и preview перезагружаются для точного target slug.
- После Sync сохраняется target slug, категория и индекс этого asset.
- Если asset исчез или перестал быть published, применяется обычный fallback
  текущей категории.
- Размещённые модели этим UI-обновлением не изменяются.
