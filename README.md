# Time Clock - User Guide

**Time Clock** is a lightweight, easy-to-use desktop time tracking application designed to help you track your work hours across tasks, distinguish between reported and unreported time, and export your records for invoicing, payroll, or personal productivity analysis.

---

## Table of Contents
1. [Getting Started & Installation](#getting-started--installation)
   - [macOS Desktop App Installation](#macos-desktop-app-installation)
   - [Pinning to macOS Dock & Taskbar](#pinning-to-macos-dock--taskbar)
   - [Migrating an Existing Database](#migrating-an-existing-database)
   - [Configuration & Custom Database Location](#configuration--custom-database-location)
   - [Updating the Application](#updating-the-application)
   - [Direct Terminal Launch](#direct-terminal-launch)
2. [Interface Overview](#interface-overview)
3. [Managing Tasks](#managing-tasks)
4. [Tracking Time](#tracking-time)
5. [Tracking Earnings & Monthly Goals](#tracking-earnings--monthly-goals)
6. [Editing Clock In/Out Times (Advanced)](#editing-clock-in-out-times-advanced)
7. [Viewing Historical Time Statistics (Calendar)](#viewing-historical-time-statistics-calendar)
8. [Managing Reported vs. Unreported Time](#managing-reported-vs-unreported-time)
9. [Viewing Session History](#viewing-session-history)
10. [Exporting Your Data](#exporting-your-data)
11. [Tips for Effective Time Tracking](#tips-for-effective-time-tracking)
12. [Frequently Asked Questions](#frequently-asked-questions)

---

## Getting Started & Installation

### macOS Desktop App Installation
You can install Time Clock directly as a standard, native macOS application without third-party app stores or complex setup:

1. Open your terminal in the `time_clock` project folder.
2. Run the installation script:
   ```bash
   ./scripts/install_macos.sh
   ```
3. The script packages and places **Time Clock.app** into your `/Applications` directory (or `~/Applications` if running without administrator permissions).
4. You can now launch Time Clock from **Spotlight** (`Cmd + Space` -> type `Time Clock`), **Launchpad**, or **Finder -> Applications**.

### Pinning to macOS Dock & Taskbar
To keep Time Clock easily accessible on your macOS taskbar/Dock:
1. Open **Finder** and navigate to **Applications** (or press `Cmd + Shift + A`).
2. Locate **Time Clock** (with the blue-and-crimson clock icon).
3. Drag and drop **Time Clock** into your Dock.
4. Alternatively, while Time Clock is running, right-click (or two-finger tap) the clock icon in your Dock, hover over **Options**, and select **Keep in Dock**.

### Migrating an Existing Database
If you have previously tracked hours in a local project database (such as `data/time_clock.db`), you can easily copy your existing data to the installed application's database location so that none of your history is lost:

```bash
# Ensure target application support directory exists
mkdir -p "$HOME/Library/Application Support/TimeClock"

# Copy your existing database file
cp data/time_clock.db "$HOME/Library/Application Support/TimeClock/time_clock.db"
```

The installed application will automatically recognize your tasks, session timestamps, and billing statuses on next launch.

### Configuration & Custom Database Location
Time Clock uses a simple, user-editable JSON configuration file located at:
- **`~/.config/time_clock/config.json`**

When the application is first launched, it automatically creates this file with standard default paths:
```json
{
  "db_path": "~/Library/Application Support/TimeClock/time_clock.db"
}
```

#### Customizing the Database Path
If you prefer storing your time tracking database in another directory (for example, in your personal Documents folder or a synchronized local folder):
1. Open `~/.config/time_clock/config.json` in any text editor.
2. Modify the `"db_path"` property to your desired path (supports `~` home directory expansion or full absolute paths):
   ```json
   {
     "db_path": "~/Documents/MyTimeTracking/time_clock.db"
   }
   ```
3. Save the file and restart Time Clock.

#### Environment Variable Overrides
For automated environments or custom scripts:
- `TIME_CLOCK_CONFIG`: Override the configuration file path (e.g., `export TIME_CLOCK_CONFIG=/path/to/custom_config.json`).
- `TIME_CLOCK_DB`: Directly override the database file path (e.g., `export TIME_CLOCK_DB=/path/to/custom_db.db`).

### Updating the Application
When new features or bug fixes are pulled from the repository, update your installed macOS application bundle in seconds:

```bash
./scripts/update_macos.sh
```

The update script syncs the newest application files into `/Applications/Time Clock.app` while leaving your personal database (`~/Library/Application Support/TimeClock/time_clock.db`) and configuration file untouched.

### Direct Terminal Launch
You can also launch Time Clock directly from the command line:
```bash
python3 main.py
```

---

## Interface Overview

The Time Clock window is organized into intuitive, switchable views accessible via the top navigation toggle button and **View** menu:

```
+------------------------------------------------------------------------+
|  Top Header: View Switcher (Switch between Time Clock & Earnings View) |
|  Top Menu: File | View | Advanced                                      |
+------------------------------------+-----------------------------------+
|  Tasks Panel (Left)                |  Clock Tracker (Top Right)        |
|  - Add new tasks (Paid / Unpaid)   |  - Active task status & timer     |
|  - 💰 Paid status indicator column |  - All Tasks Summary: Day/Week/Mo |
|  - Select, rename, archive tasks   |  - Clock In / Clock Out button    |
|  - Add Earnings... per task        |  - Mark Reported button           |
|  - Unified Edit Task dialog        |                                   |
|  - View total & unreported times   +-----------------------------------+
|                                    |  Session History (Bottom Right)   |
|                                    |  - Detailed session timestamps    |
|                                    |  - Reported vs unreported status  |
|                                    |  - Task history export & summary  |
+------------------------------------+-----------------------------------+
```

- **Top Header Bar**: Switch instantly between the **Time Clock View** and the dedicated **Earnings View**.
- **File Menu (Top Bar)**: Access global data export (CSV/JSON) and application exit.
- **View Menu (Top Bar)**: Switch between Time Clock and Earnings & Goals views.
- **Advanced Menu (Top Bar)**: Log task earnings (**Add Earnings...**), open the unified task editing dialog (**Edit Task...**), permanently delete a selected task (**Delete Task...**), or inspect historical period metrics using a calendar dialog (**Historical Time Stats...**).
- **Tasks Panel (Left Side)**: Manage your list of projects or tasks, view the `💰` paid status column, record earnings, and configure options.
- **Clock Tracker (Top Right)**: Control your live timer and see current session progress.
- **Session History (Bottom Right)**: Review logged work sessions for the selected task.

---

## Managing Tasks

The **Tasks** panel on the left allows you to organize your work into discrete tasks or projects.

### Paid vs. Unpaid Tasks
Tasks in Time Clock can be designated as either **Paid** (default) or **Unpaid**:
- **Paid (Reportable)**: Billable or client-facing tasks that accumulate unreported time as you work. Unreported time is tracked toward reporting milestones and highlighted when pending.
- **Unpaid (Non-reportable)**: Internal, non-billable, or administrative activities (e.g., internal meetings, breaks, learning). Unpaid tasks track total elapsed duration normally (contributing to task total time and Day, Week, and Month summaries) but always show `00:00:00` for Unreported Time and never appear as pending unreported work.
- **Visual Badges & Color Coding**: Unpaid tasks are clearly labeled with an `[Unpaid]` badge across the task list, active timer header, session history, and dialog dropdowns, and are visually distinguished in warm amber text.
- **Reporting Controls**: Because unpaid tasks do not accumulate reportable time, reporting actions (**Report...** in Tasks panel and **Mark Reported** in Clock Tracker) are automatically disabled when an unpaid task is selected.

### Task List & Unreported Time Indicators
The task table displays your tasks with a paid indicator column alongside their **Total Time** and **Unreported Time**:
- **Paid Indicator Column (`💰`)**: A dedicated column on the left displays a money emoji (`💰`) for paid tasks and remains blank for unpaid tasks, allowing you to instantly identify billable projects at a glance.
- **Visual Status Highlighting**: Paid tasks containing pending unreported time (`> 00:00:00`) are prominently highlighted in blue text so you can immediately see which projects need to be billed or submitted. Fully reported paid tasks appear in neutral dark text, unpaid tasks appear in distinct warm amber text, and archived tasks appear in muted gray.
- **Live Synchronization**: As you clock in, clock out, or track active work, the task's unreported time counter, paid indicator, and highlight tag update automatically in real time.
- **Aggregate Summary Indicator**: A footer summary below the task list displays the total number of projects with outstanding work and cumulative pending duration (e.g., `Unreported: 2 projects (04:15:00)`), ignoring unpaid tasks so your pending billing summary stays accurate.

### Adding a Task
1. Click the **New Task...** button at the top of the Tasks panel.
2. In the modal dialog:
   - Enter or paste the name of your task (e.g., `Client Website Redesign`, `Internal Sync`).
   - Select the task type: **Paid (Reportable)** or **Unpaid (Non-reportable)**.
3. Click **OK** or press **Enter / Return** on your keyboard.
4. Your new task appears in the task list below and is automatically selected.

### Selecting a Task
- Click on any task in the list to select it.
- Once selected, the **Clock Tracker** and **Session History** panels automatically update to show details for that task.

### Editing Task Options and Sessions (Unified Dialog)
You can change a task's name, toggle its paid/unpaid status, adjust active running timers, and edit past session records in a single unified dialog:
1. Click on the task in the list to select it.
2. Click the **Options...** button below the task list (or choose **Advanced -> Edit Task...** from the top menu bar).
3. In the unified dialog:
   - **Task Details & Options**:
     - Choose a task from the **Select Task** dropdown.
     - View and edit the full task name in the dedicated full-width **Task Name** field, providing ample space for long task names.
     - Toggle between **Paid (Reportable)** and **Unpaid (Non-reportable)** status, then click **Save Options**.
   - **Active Running Session**: If the task is running, edit the start timestamp and click **Apply Start Time**.
   - **Completed Sessions**: Select any historical session to modify start/end timestamps via **Save Changes**, or insert a missed session using **Add as New**.
4. The task list, timer panel, and session views will instantly update to reflect your changes.

### Renaming a Task
You can quickly rename a task directly:
1. Click on the task you wish to rename to highlight it.
2. Click the **Rename** button below the task list.
3. Enter the new name in the popup dialog and confirm.
4. The task list and timer header will immediately reflect the updated name.

### Archiving and Unarchiving Tasks
Archiving allows you to keep your active task list organized and focused without losing any tracked work sessions, total duration, or historical reporting metrics:
- **Archiving a Task**:
  1. Click on the task in the list that you wish to archive.
  2. Click the **Archive** button below the task list and confirm in the dialog prompt.
  3. The task is removed from the default active task list.
  4. If the task was actively clocked in when archived, the running session is automatically and safely finalized and saved.
  5. The application will automatically switch active selection to the next available unarchived task.
- **Viewing Archived Tasks**:
  - Check the **Show Archived** box at the top right of the Tasks panel.
  - Archived tasks will appear in the task list with an `[Archived]` tag and muted gray text.
- **Unarchiving a Task**:
  1. Enable the **Show Archived** checkbox.
  2. Click on the archived task you want to restore.
  3. The management button will dynamically change to **Unarchive**.
  4. Click **Unarchive** to restore the task to the active list.

### Deleting a Task
1. Click the task in the list that you wish to remove.
2. In the top application menu bar, click **Advanced** and select **Delete Task...**.
3. A confirmation dialog will ask if you are sure you want to delete the task and all of its recorded sessions.
4. Confirm to permanently remove the task.

---

## Tracking Time

The **Clock Tracker** panel in the upper right gives you full control over timing your active work sessions.

### Starting a Timer (Clock In)
1. Select the task you want to work on from the Tasks list.
2. Click the large **Clock In** button.
3. The display will change:
   - The status updates to **Status: Running (Clocked In)**.
   - The **Start Time** shows the exact time tracking began.
   - The large digital stopwatch begins counting up in `HH:MM:SS` (Hours:Minutes:Seconds).
   - The button label switches to **Clock Out**.

### Stopping a Timer (Clock Out)
1. When you pause or finish working on the task, click **Clock Out**.
2. The session ends, the timer resets to `00:00:00`, and the completed work interval is automatically saved to the **Session History** table.
3. Both **Total Time** and **Unreported Time** for the task update instantly.

### Aggregate Period Counters (Day, Week, Month)
Directly below the active task counters in the **Clock Tracker**, the **All Tasks Summary** displays your total cumulative hours across all tasks:
- **Day**: Total time logged today (starting from midnight 00:00:00 local time).
- **Week**: Total time logged during the current calendar week (starting Monday at 00:00:00).
- **Month**: Total time logged during the current calendar month (starting on the 1st of the month at 00:00:00).
- **Includes Archived Tasks**: Hours logged to archived projects are automatically included in Day, Week, and Month totals, ensuring your progress and timesheet totals remain completely accurate even when old tasks are archived.
- **Real-Time Ticking**: While clocked in, these period counters dynamically increment second-by-second alongside your active session.

### Persistent Running Timer on Exit
If you close the application window while a timer is running without clocking out, the clock continues running in the background. When you reopen Time Clock, your active session seamlessly resumes from where you left off, with your original start time and elapsed duration preserved.

---

## Tracking Earnings & Monthly Goals

Time Clock includes a dedicated **Earnings View** and seamless earnings logging integrated directly with your tasks.

### Switching Between Time Clock and Earnings Views
- Click the top navigation button (**Switch to Earnings View** / **Switch to Time Clock**) in the header bar or choose **View -> Earnings View** from the top menu bar.
- Your active clock, ticking timer, and selected task persist uninterrupted across view switches.

### Logging Earnings for Tasks
You can open the **Add Earnings** dialog in several ways:
- **Add Earnings...** button in the **Tasks** panel.
- **Advanced -> Add Earnings...** in the top menu bar.
- **Add Earnings...** button in the **Earnings View**.
- **Report...** (Tasks panel) or **Mark Reported** (Clock Tracker): opens the same dialog with **Mark task as reported** already checked.

In the dialog:
   - **Task**: Choose the task from the dropdown (the selected or active task is preselected).
   - **Earnings Amount**: Enter the monetary amount earned (e.g., `150.00`).
   - **Date Earned**: Pick the year, month, and day from the dropdowns (defaults to today), or click **📅 Pick Date...** to choose from a calendar.
   - **Note**: Optionally add notes.
   - **Mark task as reported**: Pre-checked only when opened via **Report...** / **Mark Reported**; otherwise check it yourself if desired. When checked, all work up to the moment you click **Save** is marked as reported (unreported time resets to `00:00:00`), regardless of the earned date.
   - **Advanced...**: Additional reporting actions (see [Managing Reported vs. Unreported Time](#managing-reported-vs-unreported-time)).

Click **Save**. The entry is recorded, and period statistics recompute instantly. For unpaid tasks, the reporting checkbox and **Advanced...** are disabled.

### Setting Monthly Goals & 4-Week Month Option
1. Switch to the **Earnings View** and click **Set Monthly Goal...**.
2. In the modal dialog:
   - **Monthly Target Amount**: Enter your target earnings for the month (e.g., `3000.00`).
   - **4-Week Month Option**: Check **Use 4-week month (28-day target horizon)** if you operate on 4-week budgeting or billing cycles.
     - When enabled, target requirements are calculated across the first 28 days of the month, while total earnings continue to be tracked for the full calendar month.
3. Click **Save Goal**.

### Dynamic Daily Needed Metric
The Earnings view displays how much money you need to make per remaining day in your target period:
$$\text{Needed Per Day} = \max\left(0, \frac{\text{Goal Amount} - \text{Current Month Earnings}}{\text{Remaining Target Days}}\right)$$
This statistic is recalculated dynamically each day and automatically adjusts whenever earnings are logged or deleted. Once your monthly goal is reached, the metric displays `Goal Met! 🎉`.

### Visual Milestone Progress Bars & Cycle Pace Markers
The Earnings view displays real-time progress bars for:
- **Daily Progress**: Tracks today's earnings against the daily target.
- **Weekly Progress**: Tracks the current calendar week's earnings against the weekly milestone target.
- **Monthly Progress**: Tracks total month earnings against the overall monthly goal.

#### Cycle Pace Markers & Status Feedback
When a target goal is configured, the weekly and monthly milestone progress bars display a high-contrast visual vertical pace marker indicating where your earnings should be at the current point in the cycle:
- **Weekly Pace Marker**: Marks the expected pacing position for the current day in the 7-day week (Monday through Sunday).
- **Monthly Pace Marker**: Marks the target pacing position for the current active day across your selected cycle horizon (standard calendar month or 28-day billing cycle).
- **Ahead / Behind Pacing Feedback**: Milestone labels provide real-time status feedback showing your target pacing percentage, current cycle day, and dollar delta (e.g. `+$50.00 ahead` or `-$25.00 behind`, or `On track`).
- **Goal Reached**: When you meet or exceed your monthly goal, the daily needed metric and progress displays celebrate your achievement with `Goal Met! 🎉`.

### Earnings History Ledger
Review and manage all recorded earnings transactions in the ledger table at the bottom of the Earnings view. Select any row and click **Delete Entry** to remove incorrect records with automatic recalculation.

---

## Editing Clock In/Out Times (Advanced)

If you forget to clock in on time, forget to clock out, or need to correct past timestamps, Time Clock provides a dedicated **Advanced** menu option.

### Opening the Edit Dialog
1. In the top application menu bar, click **Advanced**.
2. Select **Edit Task...**.
3. A modal dialog will appear centered over the application window.

### Selecting a Task and Editing Details
- Use the **Select Task** dropdown at the top to choose the task you wish to inspect or edit. It defaults to your currently selected task and includes any archived tasks.
- The **Task Name** is displayed on its own wide input line across the dialog width, making it convenient to read and edit long task names.
- Adjust the **Paid (Reportable)** or **Unpaid (Non-reportable)** classification and click **Save Options** to update task attributes.

### Adjusting an Active Session Start Time
If the selected task is currently clocked in:
1. The **Active Running Session** section will display your active clock-in timestamp.
2. Edit the **Start Time** field (e.g. adjust `2026-10-01 09:30:00` to `2026-10-01 09:00:00`).
3. Click **Apply Start Time**.
4. The live timer and total duration will update immediately across all panels.

### Editing Completed Session Records
1. In the **Completed Sessions** table, click on any past session to highlight and populate its timestamps into the edit fields below.
2. Modify the **Start** and/or **End** timestamp.
3. Click **Save Changes**.
4. The duration will automatically recompute, and your task totals and session history will refresh immediately.

### Adding a Missed Session Manually
1. Enter the desired **Start** and **End** timestamps in the input fields.
2. Click **Add as New**.
3. A new completed session entry is added to the task, and duration and period totals are recalculated automatically.

### Supported Timestamp Formats & Validation
- **Formats**: Supports standard ISO formats with or without the `T` separator (e.g., `2026-10-01 09:00:00` or `2026-10-01T09:00:00`).
- **Validation**:
  - Start timestamps cannot be set in the future.
  - End timestamps cannot be earlier than start timestamps.
  - Descriptive error messages are displayed if an invalid date or timestamp format is entered.

---

## Viewing Historical Time Statistics (Calendar)

Time Clock includes a historical statistics tool that allows you to inspect past time tracking metrics across all tasks for any chosen date.

### Opening Historical Time Stats
1. In the top application menu bar, click **Advanced**.
2. Select **Historical Time Stats...**.
3. A modal dialog will appear centered over the application window displaying an interactive monthly calendar and time summary statistics.

### Navigating the Calendar & Viewing Statistics
- **Month Navigation**: Use the `<` and `>` buttons at the top of the calendar to move between previous and next calendar months.
- **Selecting a Date**: Click on any past or present date in the calendar grid. The selected date will be highlighted, and the statistics section below will immediately update.
- **Time Statistics Breakdown**:
  - **Daily**: Total time tracked across all tasks for the selected 24-hour day.
  - **Weekly**: Total time tracked during the calendar week (Monday through Sunday) containing the selected day.
  - **Monthly**: Total time tracked during the calendar month containing the selected day.
- **Future Dates Restriction**: Dates in the future are disabled and cannot be clicked or selected because time tracking records and metrics only apply to past and current dates.

---

## Managing Reported vs. Unreported Time

When logging hours for client billing, contractor timesheets, or sprint reporting, you often need to know which hours have already been submitted and which hours remain unreported.

### Understanding Time Counters
- **Total Time**: The cumulative duration of all recorded sessions for the task.
- **Unreported Time**: The duration of work completed *after* your last reporting cutoff timestamp.

### Marking Time as Reported
Click the **Report...** button in the Tasks panel (or **Mark Reported** in the Clock Tracker panel) to open the **Add Earnings** dialog pre-configured to mark your task as reported.

#### Advanced Reporting Options
Within the **Add Earnings** dialog, click the **Advanced...** button to access non-monetary reporting utilities. Each action applies to the task selected in the dialog and closes the dialog immediately, without saving any earnings amount or note you entered. **Advanced...** is disabled for unpaid tasks.

1. **Mark as Reported Now (No Earnings)**:
   - Sets the reporting cutoff timestamp to the current moment.
   - Marks all sessions completed up to this point as reported without logging monetary earnings.
   - Resets the task's **Unreported Time** counter to zero.

2. **Custom Timestamp...**:
   - Allows you to set a specific cutoff date and time in standard ISO format (`YYYY-MM-DDTHH:MM:SS`).
   - Any sessions that ended at or before that timestamp will be marked as reported; sessions after that timestamp will remain unreported.

3. **Clear Reported Status**:
   - Clears the reporting cutoff for the task.
   - Returns all historical sessions to an unreported state, making your **Unreported Time** equal to your **Total Time**.

### Visual Indicators
- **Tasks List**:
  - Projects with pending unreported time (`> 00:00:00`) are highlighted in bold blue text with an aggregate unreported summary indicator in the footer.
  - Fully reported projects (`00:00:00`) appear in neutral muted text.
- **Session History Table**:
  - **Reported Sessions** are displayed in gray/dimmed text.
  - **Unreported Sessions** are displayed in normal, prominent text.

---

## Viewing Session History

The **Session History** panel in the lower right displays all individual work sessions for the currently selected task.

### Session Details Table
The history table lists each work interval with the following columns:
- **#**: Sequential session number.
- **Start Time**: Date and time the session began (`YYYY-MM-DD HH:MM:SS`).
- **End Time**: Date and time the session was stopped.
- **Duration**: Total elapsed time formatted as `HH:MM:SS`.

### History Summary Bar
The bottom footer displays a quick statistical breakdown for the active task:
- Total number of sessions logged.
- Total accumulated duration.
- Total unreported duration.

---

## Exporting Your Data

Time Clock offers flexible export options so you can easily analyze your data in spreadsheet software (such as Microsoft Excel, Google Sheets, or Apple Numbers) or integrate with other tools.

### 1. Exporting Single Task History
To export history for only the currently selected task:
1. Select the desired task from the Tasks list.
2. In the **Session History** panel, click the **Export...** button in the bottom left corner.
3. Choose your preferred file format:
   - **CSV (`.csv`)**: Ideal for spreadsheets. Includes task details, archive status, paid/unpaid (`is_unpaid`) status, start time, end time, and duration in seconds.
   - **JSON (`.json`)**: Ideal for technical workflows or importing into other tools.
4. Choose where to save the file and click **Save**.

### 2. Exporting All Application Data
To export all tasks (including active and archived projects) and all session records across the entire application at once:
1. Click the **File** menu in the top menu bar.
2. Select either:
   - **Export Data as CSV...**: Saves a comprehensive spreadsheet containing every task (with `is_archived` and `is_unpaid` status) and its complete session history.
   - **Export Data as JSON...**: Saves the complete application database in JSON format.
3. Select your destination folder and file name, then click **Save**.

---

## Tips for Effective Time Tracking

- **One Task at a Time**: Select a task before starting work to keep sessions categorized accurately.
- **Switching Tasks**: When switching projects, click **Clock Out** on the current task, select the new task in the left list, and click **Clock In**.
- **Weekly or Monthly Reporting**: At the end of each billing cycle or work week, use **Export Data as CSV...** to generate your timesheet report, then click **Report...**, enter any earnings, and click **Save** (or use **Report... -> Advanced... -> Mark as Reported Now (No Earnings)**) to start your next cycle with a clean unreported counter.
- **Accidental Exits**: Don't worry about losing running time if your computer restarts or the app is closed — active timers continue running and automatically resume when you reopen the application.

---

## Frequently Asked Questions

#### Where is my data stored?
Your data is stored locally in an embedded database file (`data/time_clock.db`) inside the application directory. No account creation or internet connection is required.

#### What happens if I forget to clock out?
If you leave a session running, you can clock out when you return. If you need to mark specific hours as already reported up to an earlier time, use **Report... -> Advanced... -> Custom Timestamp...** to set the exact cutoff moment.

#### Can I export to Excel?
Yes! Export your data as a `.csv` file via the **File -> Export Data as CSV...** menu or the history **Export...** button. You can open `.csv` files directly in Microsoft Excel, Google Sheets, LibreOffice Calc, or Apple Numbers.
