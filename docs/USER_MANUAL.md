# OCRIS User Manual

For teachers, admin staff and the Officer in Charge of Bayombong Central School.

OCRIS turns a scanned Form 137 into a digital record. You upload the scan, the system reads it, you check the values it was unsure about, and the record is saved.

## Contents

1. [Signing in and out](#1-signing-in-and-out)
2. [The screen layout](#2-the-screen-layout)
3. [What your role can do](#3-what-your-role-can-do)
4. [Dashboard](#4-dashboard)
5. [Uploading a Form 137](#5-uploading-a-form-137)
6. [Records](#6-records)
7. [Record Detail](#7-record-detail)
8. [Search](#8-search)
9. [Grade Analytics](#9-grade-analytics)
10. [Scan History](#10-scan-history)
11. [User Management](#11-user-management)
12. [Audit Log](#12-audit-log)
13. [Common questions and problems](#13-common-questions-and-problems)

---

## 1. Signing in and out

1. Open OCRIS in your browser.
2. Type your **username** and **password**.
3. Click **Sign in to OCRIS**, or press Enter.

If you see "Invalid username or password", check your typing. If you see "Can't reach the server", OCRIS is not running; tell the person who maintains it.

To sign out, click **Sign out** at the top right. Always sign out on a shared computer.

You stay signed in if you refresh the page, but an upload in progress is lost, so **do not refresh in the middle of an upload**. After 12 hours you are asked to sign in again.

### Changing your password

1. Click **Change password** at the top right.
2. Type your current password, then the new one twice. Use at least 8 characters.
3. Click **Change password**.

Change the temporary password you were given the first time you sign in. If you forget your password, ask the OIC to set a new one for you.

## 2. The screen layout

- **Left: the menu.** Click an item to open that page. Your name and role are shown at the bottom.
- **Top: the page title** and the **Sign out** button.
- **Centre: the page you opened.**

| Menu item | What it is for |
|---|---|
| Dashboard | Overview and recent uploads |
| Upload Form 137 | Digitize a scanned form |
| Records | List of all saved records |
| Search | Find a pupil's record |
| Grade Analytics | Class means, pass rates, intervention flags |
| Scan History | Every scan that has been uploaded |
| Sections | The sections in each grade level (OIC and Admin Staff) |
| User Management | Accounts (OIC; Admin Staff can view) |
| Audit Log | Who did what, and when (OIC and Admin Staff) |

## 3. What your role can do

| | OIC | Admin Staff | Teacher |
|---|---|---|---|
| Upload and validate Form 137 | Yes | Yes | Yes |
| View records | All | All | Your own class |
| Download the original scan | All | All | Your own class |
| View analytics and scan history | All | All | Your own class |
| Edit or delete records | Yes | Yes | No |
| View the audit log | Yes | Yes | No |
| Manage user accounts | Yes | No | No |

The menu shows only the pages your role can use, so a teacher's menu is shorter than the OIC's.

**Teachers:** your account must have a grade and section assigned. If you see "Your account has no class assigned yet", ask the OIC to assign them.

## 4. Dashboard

The first page after signing in.

| Item | Meaning |
|---|---|
| Digitized records | Total number of saved records you can see |
| Unfinished uploads | Uploads that were read by the system but never saved as a record |
| Intervention flags | Subjects whose class mean is below 75 |
| Recent uploads | The six newest records. Click **View** to open one. |

Coloured notices on the right tell you when something needs attention. **All clear** means there is nothing pending.

## 5. Uploading a Form 137

Click **Upload Form 137** in the menu. The upload has six steps, shown as tabs across the top. You can click a completed step to go back to it.

### Before you start: scanning the form

| | |
|---|---|
| Do | Scan at 300 DPI or higher |
| Do | Use grayscale or black-and-white mode |
| Do | Keep the paper flat, with no folds |
| Do | Make sure the whole grade table is inside the scan |
| Do | Save as **JPG or PNG** |
| Avoid | Phone camera photos; shadows cause misreads |
| Avoid | Torn or badly water-damaged forms |
| Not accepted | PDF files. Export the page as an image first. |

Each upload is one image, up to 20 MB.

### Step 1: Upload

1. Type the pupil's **Last name** and **First name**.
2. Choose the **Grade level** and **School year**.
3. Type the **Section**.
4. Type the **LRN** if you have it (optional).
5. Click the upload box to choose the scan, or drag the file onto it. A preview appears.
6. Click **Next: Check image quality**.

Type these details carefully. **The saved record uses what you type here**, not what the system reads from the scan.

### Step 2: Quality

The system examines the image and rates six things: resolution, contrast, brightness, sharpness, page tilt and ink coverage. Each is shown in green (good), amber (acceptable) or red (poor), with advice when something is wrong.

| Overall result | What to do |
|---|---|
| **Good** | Click **Run OCR**. |
| **Acceptable** | You can continue. Expect more values to check by hand. |
| **Poor — rescan recommended** | Best to click **Choose another scan** and rescan the form. You may click **Run OCR anyway**, but expect many values to check. |

Reading the form can take up to a minute. Keep the page open.

If you see an error instead:

| Message | What to do |
|---|---|
| "No grade rows were found on this scan…" | The grade table is cut off, or the wrong page was scanned. Rescan with the whole table visible. |
| "This file couldn't be read as an image…" | The file is not a JPG or PNG. Convert it and try again. |
| "OCR failed on this scan. Try rescanning it." | Rescan and try again. If it keeps happening, report it. |
| "The OCR engine … was not found on the server." | Report this to the person who maintains OCRIS. |

### Step 3: Processing

A short summary of what was read:

| | |
|---|---|
| **Auto-approved** | Values the system is confident about |
| **Flagged** | Values you need to check |
| **N/A (blank)** | Boxes that are empty on the form |

Click **View extraction results**.

### Step 4: Extraction

Every value read from the form is listed.

- **Green**: auto-approved.
- **Amber**: flagged. You will check these in the next step.
- **Grey "Blank"**: the box was empty; it is stored as N/A.

If a yellow notice says **"Check the pupil details"**, the name, section, school year or grade level on the scan does not match what you typed in step 1. Either you typed something wrong, or you chose the wrong scan. Go back to step 1 to fix it. If you are sure what you typed is right, continue.

Click **Proceed to validation**.

### Step 5: Validation

This is the most important step. The scan is shown on the left and the flagged values on the right.

For each flagged value:

1. Find it on the scan, or better, on the **paper form**.
2. Type the correct grade in the box.
3. Click **Confirm**, or press Enter.

If the box is empty on the form, click **N/A**.

"OCR read" shows what the system saw. `88 / 83` means it read two different values and could not decide. **Unreadable** means it saw ink but could not read a grade.

The counter at the top shows your progress. The save button stays disabled until every flagged value has been confirmed. To change a confirmed value, click **Edit**.

If nothing was flagged, this step says "No flags" and you can continue straight away.

### Step 6: Confirm

1. Review the **Correction summary**: what the system read, and what you entered.
2. Review the **Record summary**: pupil, grade and section, school year.
3. Tick **"I have checked all flagged fields against the physical Form 137."**
4. Click **Save record**.

To change something, click **Back and edit**.

### Record saved

You will see the new **Record ID**, the **General average** and the **Remarks**. From here you can upload another form, view all records, or view analytics.

### How the remarks are decided

| Remarks | Meaning |
|---|---|
| **Promoted** | The general average is 75 or higher and every Final grade is 75 or higher |
| **Retained** | At least one Final grade is below 75 |
| **Incomplete** | The result cannot be decided: there are no Final grades, or a Final grade was saved as something that is not a number |

The **general average** is the average of all Final grades on the form. Blank (N/A) grades are left out; they are never counted as zero.

## 6. Records

A list of saved records, newest first, 20 per page.

- **Filters:** choose a grade, section or school year. The list updates immediately. **Clear** removes the filters.
- **View:** opens the record.
- **Download:** saves the original scanned image to your computer.
- **Delete** (OIC and Admin Staff): permanently removes the record and its scanned form after you confirm. This cannot be undone.
- **Upload new:** goes to the upload page.

Teachers see only the records of their assigned grade and section.

The filters list the grades, sections and school years that saved records actually use.

## 7. Record Detail

Opened by clicking **View** on a record.

| Section | Shows |
|---|---|
| Pupil information | Name, LRN, grade level, section, school year |
| Summary | General average, remarks, who uploaded it, when it was created and last updated, scan ID |
| Grades | Q1 to Q4 and Final for each subject. A Final below 75 is shown in red. |
| Manual corrections | The values that were typed by hand during validation, if any |

**Download original form** saves the scanned image. **Back to Records** returns to the list.

### Correcting a record (OIC and Admin Staff)

1. Click **Edit record**.
2. Correct the pupil details or any grade. Leave a grade empty if it is blank on the form.
3. Click **Save changes**. The general average and remarks are recalculated.

Click **Cancel** to leave the record as it was.

## 8. Search

1. Type a pupil's name, LRN, grade level or section. Part of a name is enough.
2. Click **Search**, or press Enter.

Up to 50 matching records are shown, with the matching part of the name in bold. Click **View** to open a record. Teachers get results from their own class only.

## 9. Grade Analytics

Summaries calculated from all saved records. Choose a **School year** or **Grade level** to narrow them.

| Item | Meaning |
|---|---|
| Records analysed | Number of records included |
| School-wide average | Average of the subject means |
| Intervention flags | Number of subjects with a mean below 75 |
| Overall pass rate | Average of the pass rates across grade levels |
| Class mean by subject | Average Final grade per subject. Blue: 85 and above. Amber: 75 to 84. Red: below 75. |
| Pass rate by grade level | Share of pupils whose general average is 75 or higher. Green: 90% and above. Amber: 80 to 89%. Red: below 80%. |
| Intervention flags | Each subject whose mean is below 75, as a prompt for remedial action |

Blank (N/A) grades are excluded.

## 10. Scan History

Every scan that was uploaded and read, newest first.

| Column | Meaning |
|---|---|
| Scan ID | The scan's reference number |
| OCR confidence | How confident the system was overall. Green: 90% and above. Amber: 70 to 89%. Red: below 70%. |
| Flags | How many values needed checking |
| Outcome | **saved** if a record was made from it; **pending** if the upload was started but never saved |
| File | Download the original scan |

A **pending** scan usually means someone left the upload before the last step. Upload the form again to complete it.

## 11. User Management

For the Officer in Charge. Admin Staff can view the list but cannot change it.

### Add a user

1. Fill in **Last name**, **First name** and **Username / Employee ID**.
2. Choose the **Role**.
3. For a Teacher, choose the **Assigned grade** and **Assigned section**. This decides which records the teacher can see.
4. Type a **Temporary password** of at least 8 characters.
5. Click **Create account**.

Give the username and temporary password to the user privately.

### Edit a user

Click **Edit** to change a user's name, role, assigned grade and section, or account status, then **Save changes**.

To give a user a new password, type it in **New password**. The user is signed out everywhere and signs in with the new password. Leave the box empty to keep the current password.

A teacher shown as "No class assigned" cannot see any records until you assign a grade and section.

### Deactivate or delete

| | Deactivate | Delete |
|---|---|---|
| Can the user sign in? | No | No |
| Is the account kept? | Yes; it can be made Active again with **Edit** | No; it is gone permanently |
| Are their records kept? | Yes | Yes |

Use **Deactivate** when someone leaves or is on leave. Use **Delete** only for accounts created by mistake.

You cannot delete your own account, and the system will not let you delete the only active OIC account.

The **Role permission matrix** on this page is a quick reference to what each role can do.

## 12. Audit Log

For OIC and Admin Staff. A list of actions, newest first, with who did each one and when.

| Action | Meaning |
|---|---|
| LOGIN | Someone signed in |
| UPLOAD | A scan was uploaded and read |
| VALIDATE | A record was saved |
| EDIT | A record was changed |
| DELETE | A record was deleted |
| DOWNLOAD | An original scan was downloaded |
| CREATE_USER | An account was created |
| DELETE_USER | An account was deleted |
| EDIT_USER | An account was changed |
| RESET_PASSWORD | The OIC set a new password for a user |
| CHANGE_PASSWORD | A user changed their own password |

## 13. Common questions and problems

**I was signed out while working.**
A sign-in lasts 12 hours. Sign in again. An unfinished upload has to be started again.

**Almost every grade was flagged.**
The scan is probably low quality, or the grades are handwritten. Handwritten grades are flagged on purpose so that a person checks them. Rescanning at 300 DPI on a flatbed scanner gives the best result.

**I saved a record with a wrong grade.**
Ask the OIC or Admin Staff to open the record and correct it with **Edit record**.

**The remarks say Incomplete.**
A Final grade is missing or was saved as something that is not a number. Check the Grades table on the Record Detail page. If the record is wrong, the OIC or Admin Staff can enter the correct Final grades with **Edit record**.

**I am a teacher and I cannot see a record I uploaded.**
You only see records whose grade and section match your assigned class. Check that the grade and section you typed at upload are spelled like your assignment. Capital letters do not matter, but spelling does. The OIC or Admin Staff can correct the record's section with **Edit record**.

**The Download button says the file is no longer on the server.**
The scanned image was removed from the server. The record itself is unaffected.

**A page shows "Can't reach the server".**
OCRIS has stopped running. Tell the person who maintains it.

**I cannot find User Management or Audit Log in the menu.**
Your role is not allowed to use those pages, so they are not shown.
