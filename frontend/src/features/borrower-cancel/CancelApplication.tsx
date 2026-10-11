// Отмена заявки заёмщиком из приложения: пока деньги не выданы, обязательств нет.
import { cancelBorrowerApplication, useBorrowerAction } from "@/entities/borrower";
import { errorMessage } from "@/shared/api";
import { Button } from "@/shared/ui/Button";
import { InlineError } from "@/shared/ui/InlineError";

export function CancelApplication({ applicationId, label }: { applicationId: string; label: string }) {
  const cancel = useBorrowerAction(() => cancelBorrowerApplication(applicationId));
  return (
    <>
      {cancel.isError ? <InlineError message={errorMessage(cancel.error)} /> : null}
      <Button
        variant="ghost"
        wide
        pending={cancel.isPending}
        onClick={() => {
          cancel.mutate();
        }}
      >
        {label}
      </Button>
    </>
  );
}
