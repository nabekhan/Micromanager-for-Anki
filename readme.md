## **Micromanager for Anki**

**Micromanager** is a productivity enforcement add-on designed to eliminate distractions by locking you into your Anki study sessions until a specific goal is met. It employs aggressive "focus-yanking" and window management to ensure you don't stray from your decks.

Inspiration: [FocusForce](https://ankiweb.net/shared/info/1356589749) and [Micromanager](https://getcoldturkey.com/micromanager/)

Loved FocusForce but it was buggy and didn't do everything I needed it to. Given that it has not been updated in a while, I went ahead and made numerous changes. Please message me if you want this removed.

Code: [Github](https://github.com/nabekhan/Micromanager-for-Anki/tree/main)

---

### **Core Functionality**

When an enforcement session is active, Micromanager implements the following restrictions:

* **Focus Enforcement**: If you click away from Anki or try to minimize the window, the app will automatically maximize and bring itself back to the front.
* **Deck Locking**: You are restricted to the specific deck you started with. Attempting to navigate to other decks will force you back to the deck browser or your original session.
* **Menu Blocking**: Access to the **Add-ons** and **Switch Profile** menus is disabled during an active session to prevent escaping.
* **Anti-Exit**: Standard close events are intercepted; you cannot close Anki normally until the goal is achieved or a bypass password is entered.

---

### **Goal Types**

Sessions can be configured based on six distinct targets:

* **Time**: A countdown timer that unlocks once the allotted time has expired. The progress bar fills as time passes.
* **Correct Answers**: Stay locked in until you have answered a specific number of cards correctly.
* **New Cards**: Complete a specific number of new cards.
* **Total Reviews**: Complete a specific number of card reviews.
* **Reviews Due**: Locks you in until all currently due reviews in the selected deck are cleared.
* **Complete Deck**: Locks you in until all available new and review cards in the selected deck are cleared.

---

### **Lock Methods**

You can choose how difficult it is to "break" a session early:

* **Unlocked**: Allows you to abort the session after a simple confirmation prompt.
* **Locked**: The most restrictive mode. There is no password bypass; you **must** complete the goal to unlock Anki.
* **Random Text**: Generates a 200-character string. You must type this string perfectly (no copy-pasting allowed) to unlock early.
* **Custom Password**: Requires a user-defined password to end the session.

---

### **Keyboard Shortcuts**

* **`Ctrl + Shift + M`**: Opens the Micromanager settings menu to start or update a session.

---

### **User Interface**

Micromanager features a permanent, native-styled Heads-Up Display (HUD) at the bottom of the reviewer:

* **Persistent Bar**: When no lock is active, the HUD functions as a passive daily progress tracker showing "CARDS LEFT TODAY".
* **Progress Bar**: Visually tracks progress towards your active goal or daily completion.
* **Settings Icon**: A gear icon allows you to activate a lock or adjust an existing one.
* **Abort Session**: Accessible through the settings menu during a lock, requiring the designated lock method to stop early.

> **Note**: This add-on is tested and designed to visually complement the [Onigiri](https://ankiweb.net/shared/info/1011095603) theme, utilizing native colors and a flat, modern aesthetic.
