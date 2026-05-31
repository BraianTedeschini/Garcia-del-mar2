/* García del Mar · Pro — app.js
   Concentrado: nav scroll · reveal · floating preview ·
   stepper · turno segmentado · time-slots · submit del form. */

(() => {
  "use strict";

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  const throttle = (fn, ms = 16) => {
    let pending = false, lastArgs;
    return function (...args) {
      lastArgs = args;
      if (pending) return;
      pending = true;
      setTimeout(() => { fn.apply(this, lastArgs); pending = false; }, ms);
    };
  };

  const onReady = (cb) =>
    document.readyState !== "loading"
      ? cb()
      : document.addEventListener("DOMContentLoaded", cb, { once: true });

  // ─────────── NAV scroll ───────────
  const initNav = () => {
    const nav = $("[data-nav]");
    if (!nav) return;
    const update = () => nav.classList.toggle("is-scrolled", scrollY > 24);
    update();
    addEventListener("scroll", throttle(update, 80), { passive: true });
  };

  // ─────────── Reveal on scroll ───────────
  const initReveal = () => {
    if (!("IntersectionObserver" in window)) return;
    const targets = $$(
      ".philosophy, .menu-intro, .act, .atmosphere-head, .atmosphere-grid figure, " +
      ".space-image, .space-content, .reservation-head, .form, .footer-inner"
    );
    targets.forEach((el) => el.setAttribute("data-reveal", ""));
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-revealed");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    targets.forEach((el) => io.observe(el));
  };

  // ─────────── Floating preview (sólo Carta · sólo desktop) ───────────
  const initFloatingPreview = () => {
    if (innerWidth <= 900) return;
    const float = $("#floatingImg");
    const dishes = $$(".dish[data-img]");
    if (!float || !dishes.length) return;

    let visible = false, hideT;

    const show = (src) => {
      clearTimeout(hideT);
      if (!float.src.endsWith(src)) float.src = src;
      float.style.opacity = "1";
      float.style.transform = "translate(-50%, -50%) scale(1)";
      visible = true;
    };
    const hide = () => {
      hideT = setTimeout(() => {
        float.style.opacity = "0";
        float.style.transform = "translate(-50%, -50%) scale(0.94)";
        visible = false;
      }, 120);
    };
    const move = throttle((e) => {
      if (!visible) return;
      // Offset para que no quede pegada al cursor
      float.style.left = (e.clientX + 24) + "px";
      float.style.top  = e.clientY + "px";
    }, 16);

    dishes.forEach((d) => {
      d.addEventListener("mouseenter", () => show(d.dataset.img), { passive: true });
      d.addEventListener("mouseleave", hide, { passive: true });
      d.addEventListener("mousemove", move, { passive: true });
    });
  };

  // ─────────── Form ───────────
  const TIMES = Object.freeze({
    AM: ["12:00", "12:30", "13:00", "13:30"],
    PM: ["20:00", "20:30", "21:00", "21:30"],
  });

  const allowedTime = (t) => {
    if (!/^\d{1,2}:\d{2}$/.test(t || "")) return false;
    const [h, m] = t.split(":").map(Number);
    const min = h * 60 + m;
    return (min >= 720 && min <= 810) || (min >= 1200 && min <= 1290);
  };

  const initForm = () => {
    const form = $("#formReserva");
    if (!form) return;

    const btn       = $("#btnReserva");
    const msgEl     = $("#reservaMsg");
    const fechaIn   = $("#fecha");
    const turnoIn   = $("#turno");
    const horaIn    = $("#hora");
    const slotsEl   = $("#timeSlots");
    const timeRow   = $("#timeRow");
    const segBtns   = $$(".seg-btn");
    const personas  = $("#personas");
    const stepBtns  = $$(".stepper-btn");

    // ── Fecha mínima = hoy ──
    fechaIn.min = new Date().toISOString().slice(0, 10);

    // ── Stepper personas ──
    stepBtns.forEach((b) => {
      b.addEventListener("click", () => {
        const step = Number(b.dataset.step);
        const cur  = Number(personas.value || 0);
        const next = Math.max(1, Math.min(20, cur + step));
        personas.value = next;
      });
    });

    // ── Renderizar slots según turno ──
    const renderSlots = (turno) => {
      slotsEl.innerHTML = "";
      const slots = TIMES[turno] || [];
      slots.forEach((t) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "time-slot";
        b.textContent = t;
        b.setAttribute("role", "radio");
        b.setAttribute("aria-checked", "false");
        b.addEventListener("click", () => {
          $$(".time-slot", slotsEl).forEach((x) => x.setAttribute("aria-checked", "false"));
          b.setAttribute("aria-checked", "true");
          horaIn.value = t;
        });
        slotsEl.appendChild(b);
      });
      timeRow.hidden = false;
    };

    const pickDefaultTurno = () => {
      const m = new Date().getHours() * 60 + new Date().getMinutes();
      return m >= 16 * 60 ? "PM" : "AM";
    };

    const setTurno = (turno) => {
      turnoIn.value = turno;
      segBtns.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.turno === turno)));
      renderSlots(turno);
      // Pre-seleccionar primer slot
      const first = TIMES[turno]?.[0];
      if (first) {
        horaIn.value = first;
        const firstBtn = $(".time-slot", slotsEl);
        if (firstBtn) firstBtn.setAttribute("aria-checked", "true");
      }
    };

    segBtns.forEach((b) => {
      b.addEventListener("click", () => setTurno(b.dataset.turno));
    });

    // Inicializar con el turno por defecto
    setTurno(pickDefaultTurno());

    // ── Mensajes ──
    const showMsg = (text, type) => {
      msgEl.textContent = text;
      msgEl.className = "form-msg is-visible " + (type === "success" ? "is-success" : "is-error");
    };
    const clearMsg = () => {
      msgEl.className = "form-msg";
      msgEl.textContent = "";
    };

    // ── Submit ──
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearMsg();

      const data = {
        nombre:   form.nombre.value.trim(),
        telefono: form.telefono.value.trim(),
        fecha:    form.fecha.value,
        hora:     horaIn.value,
        turno:    turnoIn.value,
        personas: Number(personas.value),
        notas:    (form.notas.value || "").trim(),
      };

      if (!data.nombre)              return showMsg("Falta tu nombre.", "error");
      if (!data.telefono)            return showMsg("Falta el teléfono.", "error");
      if (!data.fecha)               return showMsg("Elegí una fecha.", "error");
      if (!data.turno)               return showMsg("Elegí un turno.", "error");
      if (!data.hora)                return showMsg("Elegí una hora.", "error");
      if (!allowedTime(data.hora))   return showMsg("Horario fuera de servicio.", "error");
      if (!(data.personas >= 1 && data.personas <= 20)) return showMsg("Personas debe estar entre 1 y 20.", "error");

      btn.disabled = true;
      const original = btn.querySelector(".btn-label").textContent;
      btn.querySelector(".btn-label").textContent = "Enviando…";

      const ctrl = new AbortController();
      const tid  = setTimeout(() => ctrl.abort(), 12000);

      try {
        const res = await fetch("/reservar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
          signal: ctrl.signal,
        });
        clearTimeout(tid);
        let json = null;
        try { json = await res.json(); } catch { /* noop */ }

        if (res.ok && json && json.ok) {
          showMsg("Reserva recibida. Te contactamos por WhatsApp para confirmar.", "success");
          form.reset();
          personas.value = 2;
          fechaIn.min = new Date().toISOString().slice(0, 10);
          setTurno(pickDefaultTurno());
          setTimeout(clearMsg, 7000);
        } else {
          showMsg((json && json.error) || `Error (${res.status}). Intentá de nuevo.`, "error");
        }
      } catch (err) {
        clearTimeout(tid);
        const aborted = err && err.name === "AbortError";
        showMsg(
          aborted ? "El servidor tardó demasiado. Probá de nuevo."
                  : "No se pudo conectar al servidor.",
          "error"
        );
      } finally {
        btn.disabled = false;
        btn.querySelector(".btn-label").textContent = original;
      }
    });
  };

  // ─────────── Init ───────────
  onReady(() => {
    initNav();
    initReveal();
    if (!reduceMotion) initFloatingPreview();
    initForm();
  });
})();
