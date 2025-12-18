#!/usr/bin/env python3
"""
Diálogo de comentarios simplificado pero funcional
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
from typing import Optional

def get_user_comment_working(album_title: str, artist: str) -> str:
    """
    Diálogo simple pero funcional para comentarios
    """
    result = ""

    try:
        # Crear ventana root
        root = tk.Tk()
        root.title("Comentario del Álbum")
        root.geometry("800x600")
        root.resizable(True, True)

        # Centrar ventana
        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 2
        root.geometry(f"+{x}+{y}")

        # Variable para el resultado
        comment_var = tk.StringVar()
        dialog_closed = tk.BooleanVar(value=False)

        def save_comment():
            nonlocal result
            result = text_widget.get("1.0", tk.END).strip()
            dialog_closed.set(True)
            root.quit()

        def cancel_comment():
            nonlocal result
            result = ""
            dialog_closed.set(True)
            root.quit()

        # Frame principal
        main_frame = tk.Frame(root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_text = f"Comentario para: {artist} - {album_title}"
        title_label = tk.Label(
            main_frame,
            text=title_text,
            font=("Arial", 12, "bold"),
            wraplength=700
        )
        title_label.pack(pady=(0, 10), anchor="w")

        # Instrucciones
        instructions = tk.Label(
            main_frame,
            text="Puedes usar Markdown: **negrita**, *cursiva*, `código`, ## título, - lista, [enlace](url)",
            font=("Arial", 9),
            fg="gray",
            wraplength=700
        )
        instructions.pack(pady=(0, 10), anchor="w")

        # Área de texto
        text_frame = tk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=25,
            font=("Consolas", 11)
        )
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Frame de botones
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        # Botones
        cancel_btn = tk.Button(
            button_frame,
            text="Cancelar",
            command=cancel_comment,
            padx=20,
            pady=8
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))

        save_btn = tk.Button(
            button_frame,
            text="Guardar",
            command=save_comment,
            padx=20,
            pady=8,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 9, "bold")
        )
        save_btn.pack(side=tk.RIGHT)

        # Atajos de teclado
        root.bind('<Control-Return>', lambda e: save_comment())
        root.bind('<Escape>', lambda e: cancel_comment())

        # Foco en el área de texto
        text_widget.focus_set()

        # Configurar cierre de ventana
        root.protocol("WM_DELETE_WINDOW", cancel_comment)

        # Ejecutar bucle principal
        root.mainloop()

        # Limpiar
        try:
            root.destroy()
        except:
            pass

        return result

    except Exception as e:
        print(f"Error en diálogo: {e}")

        # Fallback ultra simple
        try:
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            comment = simpledialog.askstring(
                "Comentario",
                f"Comentario para {artist} - {album_title}:",
                parent=root
            )
            root.destroy()
            return comment or ""
        except:
            return ""

# Test básico
if __name__ == "__main__":
    comment = get_user_comment_working("Test Album", "Test Artist")
    print(f"Comentario: {repr(comment)}")
