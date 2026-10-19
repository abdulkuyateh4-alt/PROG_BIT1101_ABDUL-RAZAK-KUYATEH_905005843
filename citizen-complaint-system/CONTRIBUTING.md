# Contributing to CCS

Thank you for helping to improve the Citizen Complaint System.

1. Fork the repository and create a branch for your change.
2. Keep the privacy rules: **never add fields that identify a citizen**
   (names, phone numbers, ID numbers or email addresses), keep the
   personal-data check on all free text, and keep corruption reports
   confidential.
3. Follow PEP 8, add type hints and a docstring to every new class and method.
4. Add or update tests in `tests/` and make sure they all pass:
   `python -m unittest discover -v`
5. Open a pull request that explains what you changed and why.

Ideas that would help most: translating the interface into Krio, Mende,
Temne and Limba, secure storage with officer log-in, and an SMS/USSD channel.
