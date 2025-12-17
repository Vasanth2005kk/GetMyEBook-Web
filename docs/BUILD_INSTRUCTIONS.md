# Build System Fixes & Instructions

## Issues Resolved

### 1. `node-sass` Incompatibility
The project was originally using `node-sass`, which is now deprecated and frequently causes compatibility issues with newer Node.js versions and operating systems (specifically the "Unsupported runtime" error you encountered).

**Fix**:
- Uninstalled `node-sass`.
- Installed `sass` (Dart Sass), which is the modern, supported implementation.
- Updated `webpack.config.js` to use the new `sass` implementation in the `sass-loader` options.

### 2. Incorrect Output Directory
Webpack was configured to output the compiled bundled files to `cps/forum/public/js`. However, the Django/Python web application expects static files to be in `cps/static/forum/js`. Without this change, the website would continue serving old, stale JavaScript files.

**Fix**:
- Updated `webpack.config.js` output path:
  ```javascript
  output: {
      path: path.resolve(__dirname, '../static/forum/js'),
      filename: '[name].js'
  },
  ```

## How to Build the Assets

To rebuild the frontend assets (Vue components, SCSS, JS) in the future, follow these steps:

### 1. Navigate to the Forum Directory
```bash
cd cps/forum
```

### 2. Install Dependencies (First time only)
If you haven't installed them yet:
```bash
npm install
```

### 3. Development Build (Watch Mode)
This acts as a "Hot Reload". It will watch your files for changes and automatically rebuild them. Use this while you are coding.
```bash
npm run dev
```
*Note: This command runs indefinitely. Press `Ctrl+C` to stop it.*

### 4. Production Build
Run this before deploying or if you just want to build the files once without watching.
```bash
npm run prod
```
