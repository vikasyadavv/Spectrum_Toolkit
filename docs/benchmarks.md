# Benchmarks

How the methods compare, measured on simulated spectra whose true answer is known (and on the real files in `data/` where useful). These numbers are why the defaults are what they are. **This file is generated; do not edit it by hand.** Rerun with:

```
uv run python benchmarks/run_all.py
```

Generated 2026-10-21 with spectrum_toolkit 0.0.1, Python 3.13.16, numpy 2.5.4, scipy 1.18.1.

Simulated spectra (benchmarks/_simulate.py): points every 1.19 cm-1 from 100 to 1800 cm-1, Lorentzian bands 8-20 cm-1 wide, photon noise plus 15 counts read noise, like the real data.

Contents: [Cosmic-ray removal (despike)](#cosmic-ray-removal-despike), [Baseline correction](#baseline-correction), [Smoothing](#smoothing), [Normalisation](#normalisation), [Derivatives](#derivatives)

## Cosmic-ray removal (despike)

300 simulated spectra (12 bands each) get 1-3 spikes, 1-3 points wide, of
known size (5-40 x the local noise). A spike counts as repaired when every
spike point ends within 5 noise units of the clean spectrum. A false alarm
is any changed point more than 3 points away from a spike. A published
method (Whitaker & Hayes 2018) is included for reference.

Spikes repaired, by spike size in noise units, and false alarms (300 spectra, seed 1).

| method | weak <10 | medium 10-20 | strong >20 | spectra with a false alarm | false points per spectrum |
|---|---|---|---|---|---|
| single (default, threshold 8) | 14% | 69% | 94% | 1% | 0.02 |
| single, threshold 6 | 33% | 85% | 95% | 21% | 1.12 |
| single, threshold 12 | 10% | 26% | 92% | 0% | 0.00 |
| single, sharpness 0.5 | 14% | 69% | 94% | 2% | 0.12 |
| kalkan (MATLAB spikeRemoval.m) | 42% | 61% | 59% | 7% | 0.16 |
| Whitaker-Hayes 2018 (reference only) | 17% | 26% | 39% | 99% | 4.87 |

Read: "single" repairs most medium and strong spikes and almost never touches a real band. Lower threshold = more weak spikes caught but more false alarms. Weak spikes (<10x noise) are hard to tell from noise for every method.

_Script: `benchmarks/despike.py`, 3 s._

## Baseline correction

30 simulated spectra of each background kind (curved polynomial,
fluorescence decay, broad humps) with 12 bands. Error = root-mean-square
difference between the found and the true baseline, divided by the noise
(square root of the mean baseline). 1 = as good as the noise allows.

Error in noise units with default settings (lower is better; median of 30 spectra per kind, seed 0).

| method | default | polynomial | fluorescence | humps |
|---|---|---|---|---|
| **asls** | lam=100000 | 3.8 | 2.3 | 2.4 |
| **iasls** | lam=10000 | 2.0 | 2.0 | 2.2 |
| **arpls** | lam=1e+06 | 2.5 | 1.8 | 1.9 |
| **airpls** | lam=1e+06 | 1.6 | 1.2 | 1.4 |
| **modpoly** | order=5 | 2.2 | 1.3 | 2.4 |
| **imodpoly** | order=5 | 3.8 | 2.6 | 3.2 |
| **rollingball** | window=100 | 4.2 | 2.6 | 2.9 |
| **snip** | window=100 | 1.9 | 1.8 | 3.9 |

Effect of the main setting:

| method | setting | polynomial | fluorescence | humps |
|---|---|---|---|---|
| asls | lam=1000 | 8.8 | 6.0 | 6.2 |
| asls | lam=10000 | 5.8 | 3.8 | 4.0 |
| asls | lam=100000 | 3.8 | 2.3 | 2.4 |
| asls | lam=1e+06 | 2.4 | 1.5 | 1.6 |
| asls | lam=1e+07 | 1.5 | 1.4 | 4.1 |
| iasls | lam=1000 | 2.6 | 2.1 | 2.0 |
| iasls | lam=10000 | 2.0 | 2.0 | 2.2 |
| iasls | lam=100000 | 2.0 | 2.3 | 5.9 |
| iasls | lam=1e+06 | 2.2 | 4.0 | 12.3 |
| iasls | lam=1e+07 | 4.4 | 6.7 | 16.9 |
| arpls | lam=1000 | 7.0 | 5.2 | 5.3 |
| arpls | lam=10000 | 4.8 | 3.4 | 3.6 |
| arpls | lam=100000 | 3.6 | 2.5 | 2.6 |
| arpls | lam=1e+06 | 2.5 | 1.8 | 1.9 |
| arpls | lam=1e+07 | 2.0 | 1.5 | 1.7 |
| airpls | lam=1000 | 6.3 | 5.2 | 5.4 |
| airpls | lam=10000 | 4.3 | 3.0 | 3.3 |
| airpls | lam=100000 | 2.9 | 1.8 | 1.8 |
| airpls | lam=1e+06 | 1.6 | 1.2 | 1.4 |
| airpls | lam=1e+07 | 1.1 | 1.1 | 4.8 |
| modpoly | order=2 | 1.0 | 1.2 | 10.4 |
| modpoly | order=3 | 1.2 | 0.9 | 5.2 |
| modpoly | order=4 | 1.9 | 1.1 | 3.4 |
| modpoly | order=5 | 2.2 | 1.3 | 2.4 |
| modpoly | order=6 | 2.5 | 1.6 | 1.9 |
| imodpoly | order=2 | 2.9 | 2.4 | 7.4 |
| imodpoly | order=3 | 3.2 | 2.3 | 4.9 |
| imodpoly | order=4 | 3.6 | 2.4 | 3.8 |
| imodpoly | order=5 | 3.8 | 2.6 | 3.2 |
| imodpoly | order=6 | 4.0 | 2.6 | 3.1 |
| rollingball | window=50 | 7.9 | 5.3 | 6.1 |
| rollingball | window=100 | 4.2 | 2.6 | 2.9 |
| rollingball | window=150 | 2.5 | 2.1 | 2.1 |
| rollingball | window=200 | 1.9 | 2.0 | 1.9 |
| rollingball | window=300 | 1.5 | 2.4 | 2.3 |
| snip | window=50 | 3.6 | 2.3 | 2.5 |
| snip | window=100 | 1.9 | 1.8 | 3.9 |
| snip | window=150 | 3.0 | 2.8 | 10.2 |
| snip | window=200 | 4.6 | 5.2 | 15.2 |
| snip | window=300 | 7.5 | 12.0 | 22.5 |

_Script: `benchmarks/baseline.py`, 6 s._

## Smoothing

30 simulated spectra with 12 bands on a flat background. Two numbers:
error = root-mean-square difference from the clean spectrum in noise units
(the raw data scores about 1.2); height lost = how much of a narrow band's
height (FWHM < 11 cm-1) the smoother removed, in %. A good smoother has both
low.

Default settings (30 spectra, seed 0; raw data error 1.23).

| method | error (noise units) | narrow-band height lost % |
|---|---|---|
| **savgol** | 0.64 | 4.4 |
| **whittaker** | 0.64 | 5.8 |
| **spline** | 0.68 | 2.3 |
| **gaussian** | 0.70 | 4.6 |
| **moving** | 0.74 | 8.8 |
| **median** | 0.80 | 7.2 |
| **fourier** | 0.63 | 4.1 |

Effect of the settings:

| method | settings | error | height lost % |
|---|---|---|---|
| savgol | window=7, order=2 | 0.71 | 1.9 |
| savgol | window=7, order=4 | 0.93 | 0.3 |
| savgol | window=11, order=2 | 0.65 | 6.8 |
| savgol | window=11, order=4 | 0.71 | 1.5 |
| savgol | window=15, order=2 | 0.94 | 12.9 |
| savgol | window=15, order=4 | 0.64 | 4.4 |
| savgol | window=21, order=2 | 1.75 | 22.6 |
| savgol | window=21, order=4 | 0.83 | 10.0 |
| whittaker | lam=1 | 0.66 | 3.1 |
| whittaker | lam=3 | 0.64 | 5.8 |
| whittaker | lam=10 | 0.84 | 10.8 |
| whittaker | lam=30 | 1.30 | 17.1 |
| whittaker | lam=100 | 2.12 | 25.8 |
| spline | lam=None | 0.68 | 2.3 |
| gaussian | sigma=1 | 0.70 | 4.6 |
| gaussian | sigma=1.5 | 0.75 | 8.8 |
| gaussian | sigma=2 | 0.99 | 13.4 |
| gaussian | sigma=3 | 1.72 | 22.4 |
| moving | window=3 | 0.73 | 3.6 |
| moving | window=5 | 0.74 | 8.8 |
| moving | window=7 | 1.06 | 15.1 |
| moving | window=9 | 1.52 | 21.4 |
| median | window=3 | 0.89 | 2.8 |
| median | window=5 | 0.80 | 7.2 |
| median | window=7 | 0.91 | 13.2 |
| fourier | cutoff=0.1 | 2.36 | 25.3 |
| fourier | cutoff=0.15 | 1.13 | 13.3 |
| fourier | cutoff=0.25 | 0.63 | 4.1 |
| fourier | cutoff=0.4 | 0.73 | 0.9 |

Read: more smoothing lowers the error until bands start to lose height; Savitzky-Golay keeps band height best for the noise it removes.

_Script: `benchmarks/smooth.py`, 12 s._

## Normalisation

Groups of 10 replicates of the same simulated spectrum, each multiplied by
a random factor 0.5-2 (laser power, focus), in four scenarios:
  scale     only the factor
  offset    factor plus a random constant offset 0-800 counts
  slope     factor, offset and a random sloping background
  changing  factor, plus one band (600 cm-1) whose height really changes
            (e.g. a concentration series); spread is measured away from it
Spread = how different the normalised replicates still are: root-mean-square
standard deviation across replicates divided by the standard deviation of
the mean spectrum, in %. Lower is better; noise alone gives about 3.4 %.
A band at 1000 cm-1 is the same in every replicate (internal standard).

Real data: the repeat spectra in data/ (local only) after despiking.

Spread of replicates in % (lower is better; noise floor about 3.4; median of 20 groups, seed 0).

| method | scale | offset | slope | changing band |
|---|---|---|---|---|
| none (raw) | 39.9 | 47.5 | 54.4 | 38.2 |
| max | 3.7 | 29.1 | 42.3 | 60.7 |
| minmax | 4.3 | 5.8 | 42.3 | 60.2 |
| area | 3.4 | 29.2 | 40.3 | 16.2 |
| vector | 3.4 | 22.6 | 38.3 | 27.2 |
| snv (default) | 3.4 | 4.3 | 34.6 | 27.0 |
| rsnv | 6.2 | 10.1 | 71.8 | 12.3 |
| band, region 985-1015 | 4.1 | 34.4 | 47.9 | 4.7 |
| max, region 985-1015 | 3.8 | 26.5 | 42.5 | 4.1 |
| msc | 3.4 | 4.3 | 37.2 | 33.8 |
| emsc, order 1 | 3.4 | 4.3 | 6.0 | 34.0 |
| emsc (order 2) | 3.4 | 4.3 | 5.5 | 33.9 |
| pqn | 3.4 | 52.9 | 51.8 | 3.9 |

Read: every method fixes a pure scale change. Offsets need snv/msc/emsc (or baseline correction first); a sloping background needs emsc. When some bands really change, one-factor methods are pulled by them; pqn or an internal-standard band (band, or max with a region) stay right.

Real repeats (despiked, airpls baseline, then normalised): spread in %.

| file | none | max | area | vector | snv | rsnv | msc | emsc | pqn |
|---|---|---|---|---|---|---|---|---|---|
| CV10-4M.xlsx (14 spectra) | 42.7 | 17.0 | 16.6 | 16.3 | 16.1 | 18.7 | 16.2 | 15.6 | 16.7 |
| RhB10-4M.xlsx (11 spectra) | 46.7 | 45.4 | 37.5 | 36.3 | 35.1 | 43.6 | 35.5 | 34.7 | 38.8 |
| MB 10-4M.xlsx (5 spectra) | 10.5 | 9.4 | 9.4 | 8.8 | 8.7 | 12.2 | 8.7 | 8.6 | 9.9 |

Read: normalising removes most of the spot-to-spot intensity difference in CV (42 % to about 16 %); what is left in RhB is a real change in band ratios, which normalisation cannot (and should not) remove.

_Script: `benchmarks/normalize.py`, 1 s._

## Derivatives

30 simulated spectra with 12 Lorentzian bands, whose exact 1st and 2nd
derivatives are known from the formula. Error = root-mean-square difference
from the exact derivative, in % of the root-mean-square exact derivative.
Lower is better; differentiation amplifies noise, so 2nd derivatives are
always worse than 1st.

Error in % with default settings (30 spectra, seed 0).

| method | 1st derivative | 2nd derivative |
|---|---|---|
| **savgol** | 13.1 | 35.3 |
| **gaussian** | 15.5 | 39.5 |
| **spline** | 13.7 | 53.6 |
| **gradient** | 25.1 | 64.2 |

Effect of the settings:

| method | settings | 1st derivative | 2nd derivative |
|---|---|---|---|
| savgol | window=9, order=2 | 27.3 | 44.6 |
| savgol | window=9, order=3 | 13.6 | 44.7 |
| savgol | window=9, order=4 | 13.7 | 47.9 |
| savgol | window=9, order=5 | 22.8 | 51.8 |
| savgol | window=9, order=6 | 23.3 | 131.2 |
| savgol | window=11, order=2 | 35.6 | 54.6 |
| savgol | window=11, order=3 | 13.6 | 54.6 |
| savgol | window=11, order=4 | 13.8 | 35.3 |
| savgol | window=11, order=5 | 16.1 | 36.5 |
| savgol | window=11, order=6 | 16.6 | 72.5 |
| savgol | window=15, order=2 | 49.9 | 70.7 |
| savgol | window=15, order=3 | 22.0 | 70.7 |
| savgol | window=15, order=4 | 22.0 | 42.2 |
| savgol | window=15, order=5 | 13.1 | 42.5 |
| savgol | window=15, order=6 | 13.3 | 36.7 |
| savgol | window=21, order=2 | 65.8 | 84.2 |
| savgol | window=21, order=3 | 36.9 | 84.2 |
| savgol | window=21, order=4 | 36.9 | 62.2 |
| savgol | window=21, order=5 | 20.7 | 62.2 |
| savgol | window=21, order=6 | 20.7 | 43.2 |
| gaussian | sigma=0.75 | 20.0 | 109.6 |
| gaussian | sigma=1 | 15.8 | 52.0 |
| gaussian | sigma=1.25 | 15.5 | 39.5 |
| gaussian | sigma=1.5 | 18.3 | 39.5 |
| gaussian | sigma=2 | 25.5 | 49.8 |
| gaussian | sigma=3 | 40.9 | 68.6 |

Read: Savitzky-Golay is best for both; its defaults (window 15 / order 5 for n=1, window 11 / order 4 for n=2) are the best rows above. The spline is as good for a 1st derivative but poor for a 2nd. Plain finite differences (gradient) only suit data that is already smooth.

_Script: `benchmarks/derivative.py`, 13 s._
