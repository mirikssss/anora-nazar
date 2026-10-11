// Сброс демо: удаление своей песочницы во всех сервисах и возврат на вход.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { deleteSandbox, sessionStore } from "@/entities/session";
import { errorMessage } from "@/shared/api";
import { IconReset } from "@/shared/icons";
import { ru } from "@/shared/i18n/ru";
import { Button } from "@/shared/ui/Button";
import { Dialog } from "@/shared/ui/Dialog";
import { InlineError } from "@/shared/ui/InlineError";

export function ResetDemo() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const reset = useMutation({
    mutationFn: deleteSandbox,
    onSuccess: async () => {
      sessionStore.clear();
      queryClient.clear();
      setOpen(false);
      await navigate("/");
    },
  });

  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        icon={IconReset}
        iconOnlyOnPhone
        onClick={() => {
          setOpen(true);
        }}
      >
        {ru.shell.resetDemo}
      </Button>
      <Dialog
        open={open}
        title={ru.shell.resetTitle}
        closeLabel={ru.common.close}
        onClose={() => {
          setOpen(false);
        }}
        footer={
          <>
            <Button
              onClick={() => {
                setOpen(false);
              }}
            >
              {ru.common.cancel}
            </Button>
            <Button
              variant="primary"
              pending={reset.isPending}
              onClick={() => {
                reset.mutate();
              }}
            >
              {ru.shell.resetConfirm}
            </Button>
          </>
        }
      >
        <p>{ru.shell.resetBody}</p>
        {reset.isError ? <InlineError message={errorMessage(reset.error)} /> : null}
      </Dialog>
    </>
  );
}
