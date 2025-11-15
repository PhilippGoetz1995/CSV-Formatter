<h1 align="center">
  <br>
  <a href="https://p-goetz.de/"><img src="https://p-goetz.de/wp-content/uploads/2025/04/20250404_P-Goetz_DEV_logo.png" alt="P-Goetz" width="200"></a>
</h1>

<h4 align="center">📦 P-Goetz CSV Formatter</h4>

<p align="center">
  <a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/Version-1.0.0-blue"></a>
  <a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/Author-Philipp_Goetz-yellow"></a>
  <a href="https://p-goetz.de/"><img src="https://img.shields.io/badge/uptime-100%25-brightgreen"></a>

</p>

<p align="center">
  <a href="#-Architecture">Architecture</a> •
  <a href="#-how-to-use">How To Use</a> •
  <a href="#-hints-to-not-cry-everytime">Hints</a>
</p>

<!-- Screenshot is optional -->
<!-- ![screenshot](https://raw.githubusercontent.com/amitmerchant1990/electron-markdownify/master/app/img/markdownify.gif) -->

---

Tool for Uploading a CSV & Formatting it => then download a cleaned CSV:
- Numbers → configurable separators & decimal places
- Dates → normalized to **YYYY-MM-DD**
- Phone numbers → normalized to **E.164** (`+491701234567`)
- Addresses → extract **ISO-3166-2** codes (e.g., `US-CA`, `DE-BY`)

---

<!-- GETTING STARTED -->
## 🏗️ Architecture

### Frontend
- Python Streamlit & Pandas

### Backend
- AWS EC2 Instance

### CI/CD Workflow
* Github Action Workflow on push to main
* Upload to EC2 Instance

<br>

## 🔧 How To Use

## Commands

```bash
# Start streamlit Application
python -m streamlit run app_v1.0.0.py
```

<br>

## 🤬 Hints to not cry everytime

- ...

<br>

## 📅 Version History

<details>
<summary><strong>v1.0.0</strong> – 15.11.2025</summary>

- 🔧 Fixed some smaller issues with the Adress Mapping

</details>

<details>
<summary><strong>v0.0.1</strong> – 14.11.2025</summary>

- 🔧 First Version

</details>