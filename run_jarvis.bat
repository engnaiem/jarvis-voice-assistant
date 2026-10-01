@echo off
title J.A.R.V.I.S. Background Service

:: 1. الانتقال لمجلد المشروع
cd /d "C:\AI_Projects\my_first_project"

:: 2. تفعيل البيئة الافتراضية (تأكد أن اسم المجلد هو venv، وإذا كان غير ذلك غيره هنا)
call venv\Scripts\activate

:: 3. تشغيل السكربت مع تمرير باراميتر الصوت إذا احتجت
python jarvis_offline.py --voice

pause