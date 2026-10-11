// Состояние страницы банка в адресе: выбранная заявка, операция, вкладка. Меняем одни ключи, не теряя других.
import { useSearchParams } from "react-router";

export function usePageParams() {
  const [params, setParams] = useSearchParams();
  const patch = (values: Readonly<Record<string, string | null>>) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(values)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };
  return { get: (key: string) => params.get(key), patch };
}
